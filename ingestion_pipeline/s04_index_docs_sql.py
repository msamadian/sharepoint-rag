import os
import json
import requests
import nltk
import pyodbc

from requests_ntlm import HttpNtlmAuth
from sentence_transformers import SentenceTransformer
from nltk.tokenize import sent_tokenize
from urllib.parse import quote
from dotenv import load_dotenv


load_dotenv()


# SharePoint Configuration

SHAREPOINT_URL = os.getenv("SHAREPOINT_URL")
SHAREPOINT_USERNAME = os.getenv("SHAREPOINT_USERNAME")
SHAREPOINT_PASSWORD = os.getenv("SHAREPOINT_PASSWORD")

SHAREPOINT_FOLDER = "/Docs"


# SQL Server Configuration

SQL_SERVER = os.getenv("SQL_SERVER")
SQL_DATABASE = os.getenv("SQL_DATABASE")

# Windows Authentication
SQL_CONNECTION_STRING = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    f"SERVER={SQL_SERVER};"
    f"DATABASE={SQL_DATABASE};"
    "Trusted_Connection=yes;"
    "TrustServerCertificate=yes;"
)


# Embedding Configuration

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL")
EMBEDDING_DIMENSIONS = int(os.getenv("EMBEDDING_DIMENSIONS"))
MAX_CHUNK_TOKENS = int(os.getenv("MAX_CHUNK_TOKENS"))
OVERLAP_TOKENS = int(os.getenv("OVERLAP_TOKENS"))


# Load embedding model

print("Loading embedding model...")

model = SentenceTransformer(EMBEDDING_MODEL)

tokenizer = model.tokenizer

print("Embedding model loaded.")


# NLTK

def initialize_nltk():

    try:
        sent_tokenize("Test sentence.")

    except LookupError:

        print("Downloading NLTK punkt tokenizer...")

        nltk.download("punkt")
        nltk.download("punkt_tab")


# Token counting

def count_tokens(text):

    tokens = tokenizer.encode(
        text,
        add_special_tokens=False
    )

    return len(tokens)


# Chunking

def chunk_document_by_sentences(
    document,
    max_chunk_size=MAX_CHUNK_TOKENS,
    overlap_tokens=OVERLAP_TOKENS
):

    sentences = sent_tokenize(document)

    chunks = []

    current_chunk = []
    current_tokens = 0

    for sentence in sentences:

        sentence_tokens = count_tokens(sentence)

        # Sentence itself is unusually large

        if sentence_tokens > max_chunk_size:

            # First save existing chunk
            if current_chunk:

                chunks.append(
                    " ".join(current_chunk)
                )

                current_chunk = []
                current_tokens = 0

            # Tokenize large sentence
            token_ids = tokenizer.encode(
                sentence,
                add_special_tokens=False
            )

            start = 0

            while start < len(token_ids):

                end = start + max_chunk_size

                chunk_ids = token_ids[start:end]

                chunk_text = tokenizer.decode(
                    chunk_ids,
                    skip_special_tokens=True
                )

                chunks.append(chunk_text)

                start += (
                    max_chunk_size -
                    overlap_tokens
                )

            continue

        # Normal sentence

        if (
            current_tokens + sentence_tokens
            > max_chunk_size
            and current_chunk
        ):

            chunks.append(
                " ".join(current_chunk)
            )

            # Build overlap
            overlap_sentences = []
            overlap_size = 0

            for previous_sentence in reversed(
                current_chunk
            ):

                tokens = count_tokens(
                    previous_sentence
                )

                if (
                    overlap_size + tokens
                    > overlap_tokens
                ):
                    break

                overlap_sentences.insert(
                    0,
                    previous_sentence
                )

                overlap_size += tokens

            current_chunk = overlap_sentences

            current_tokens = overlap_size

        current_chunk.append(sentence)

        current_tokens += sentence_tokens

    # Last chunk
    if current_chunk:

        chunks.append(
            " ".join(current_chunk)
        )

    return chunks


# SharePoint session

def create_sharepoint_session():

    session = requests.Session()

    session.auth = HttpNtlmAuth(
        SHAREPOINT_USERNAME,
        SHAREPOINT_PASSWORD
    )

    session.headers.update({
        "Accept": "application/json;odata=verbose"
    })

    return session


# Get SharePoint library documents

def get_sharepoint_files(session):

    safe_folder = SHAREPOINT_FOLDER.replace(
        "'",
        "''"
    )

    url = (
        f"{SHAREPOINT_URL}"
        f"/_api/web/"
        f"GetFolderByServerRelativeUrl("
        f"'{safe_folder}')"
        f"/Files"
    )

    response = session.get(url)

    response.raise_for_status()

    data = response.json()

    files = data["d"]["results"]

    txt_files = [
        file
        for file in files
    ]

    return txt_files


# Download one SharePoint file

def download_sharepoint_file(
    session,
    server_relative_url
):

    url = (
        f"{SHAREPOINT_URL}"
        f"/_api/web/"
        f"GetFileByServerRelativeUrl("
        f"'{server_relative_url}')"
        f"/$value"
    )

    response = session.get(url)

    response.raise_for_status()

    return response.content.decode(
        "utf-8"
    )


# Extract title

def extract_title(content, filename):

    first_line = content.splitlines()[0].strip()

    if first_line.lower().startswith("title:"):

        return first_line[
            len("title:"):
        ].strip()

    return os.path.splitext(
        filename
    )[0]


# Extract Address

def get_file_address(server_relative_url):

    encoded_url = quote(
        server_relative_url,
        safe="/"
    )

    return (
        f"{SHAREPOINT_URL.rstrip('/')}"
        f"{encoded_url}"
    )


# Generate embeddings

def generate_embeddings(chunks):

    embeddings = model.encode(
        chunks,
        normalize_embeddings=True,
        show_progress_bar=False
    )

    return embeddings


# SQL connection

def create_sql_connection():

    return pyodbc.connect(
        SQL_CONNECTION_STRING
    )


# Delete existing chunks

def delete_existing_chunks(
    cursor,
    file_address
):

    cursor.execute(
        """
        DELETE FROM dbo.DocumentChunks
        WHERE FileAddress = ?
        """,
        file_address
    )


# Insert chunks

def insert_chunks(
    cursor,
    filename,
    file_address,
    title,
    chunks,
    embeddings
):

    sql = f"""
        INSERT INTO dbo.DocumentChunks
        (
            FileName,
            FileAddress,
            Title,
            ChunkIndex,
            Content,
            Embedding
        )
        VALUES
        (
            ?,
            ?,
            ?,
            ?,
            ?,
            CAST(
                CAST(? AS VARCHAR(MAX))
                AS VECTOR({EMBEDDING_DIMENSIONS})
            )
        )
    """

    for chunk_index, (chunk, embedding) in enumerate(
        zip(chunks, embeddings)
    ):

        embedding_json = json.dumps(
            embedding.tolist()
        )

        cursor.execute(
            sql,
            filename,
            file_address,
            title,
            chunk_index,
            chunk,
            embedding_json
        )


# Process document

def process_document(
    session,
    cursor,
    file
):

    filename = file["Name"]

    server_relative_url = (
        file["ServerRelativeUrl"]
    )

    file_address = get_file_address(
        server_relative_url
    )

    print()
    print("----------------------------------------")
    print(f"Processing: {filename}")
    print(f"Address:    {file_address}")

    # Download document from SharePoint

    content = download_sharepoint_file(
        session,
        server_relative_url
    )

    # Extract title

    title = extract_title(
        content,
        filename
    )

    print(f"Title:      {title}")

    # Chunk document

    chunks = chunk_document_by_sentences(
        content
    )

    print(
        f"Chunks:     {len(chunks)}"
    )

    # Generate embeddings

    embeddings = generate_embeddings(
        chunks
    )

    print(
        f"Embeddings: "
        f"{len(embeddings)} x "
        f"{len(embeddings[0])}"
    )


    # Delete previous version

    delete_existing_chunks(
        cursor,
        file_address
    )

    # Insert new version

    insert_chunks(
        cursor,
        filename,
        file_address,
        title,
        chunks,
        embeddings
    )

    print("Indexed successfully.")



# Main indexing process

def index_documents():

    initialize_nltk()

    print()
    print("Connecting to SharePoint...")

    sp_session = create_sharepoint_session()

    files = get_sharepoint_files(
        sp_session
    )

    print(
        f"Found {len(files)} files."
    )

    print()
    print("Connecting to SQL Server...")

    sql_connection = create_sql_connection()

    cursor = sql_connection.cursor()

    print("Connected to SQL Server.")

    successful = 0
    failed = 0

    for file in files:

        try:

            process_document(
                sp_session,
                cursor,
                file
            )

            # Commit per document
            sql_connection.commit()

            successful += 1

        except Exception as e:

            sql_connection.rollback()

            failed += 1

            print(
                f"FAILED: {file['Name']}"
            )

            print(e)

    cursor.close()
    sql_connection.close()

    print()
    print("INDEXING COMPLETED")
    print(f"Documents indexed: {successful}")
    print(f"Documents failed:  {failed}")


# Main

def main():

    index_documents()


if __name__ == "__main__":
    main()