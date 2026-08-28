import os
import json
import pyodbc

from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer


load_dotenv()


# SQL Server configuration

SQL_SERVER = os.getenv("SQL_SERVER")
SQL_DATABASE = os.getenv("SQL_DATABASE")

SQL_CONNECTION_STRING = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    f"SERVER={SQL_SERVER};"
    f"DATABASE={SQL_DATABASE};"
    "Trusted_Connection=yes;"
    "TrustServerCertificate=yes;"
)


# Embedding configuration

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL")

EMBEDDING_DIMENSIONS = int(os.getenv("EMBEDDING_DIMENSIONS"))


# Search configuration

DOCUMENT_TOP_K = int(os.getenv("DOCUMENT_TOP_K"))
LIST_TOP_K = int(os.getenv("LIST_TOP_K"))


# Load embedding model

print("Loading embedding model...")

model = SentenceTransformer(EMBEDDING_MODEL)

print("Embedding model loaded.")


# SQL connection

def create_sql_connection():

    return pyodbc.connect(
        SQL_CONNECTION_STRING
    )


# Generate query embedding

def generate_query_embedding(query):

    embedding = model.encode(
        query,
        normalize_embeddings=True,
        show_progress_bar=False
    )

    return embedding


# Convert embedding to SQL vector string

def embedding_to_json(embedding):

    return json.dumps(
        embedding.tolist()
    )


# Search document chunks

def search_document_chunks(
    cursor,
    embedding_json,
    top_k
):

    sql = f"""
        SELECT TOP {int(top_k)}
            FileName,
            FileAddress,
            Title,
            ChunkIndex,
            Content,

            VECTOR_DISTANCE(
                'cosine',
                Embedding,
                CAST(
                    CAST(? AS VARCHAR(MAX))
                    AS VECTOR({EMBEDDING_DIMENSIONS})
                )
            ) AS Distance

        FROM dbo.DocumentChunks

        WHERE Embedding IS NOT NULL

        ORDER BY Distance ASC
    """

    cursor.execute(
        sql,
        embedding_json
    )

    rows = cursor.fetchall()

    results = []

    for row in rows:

        results.append({
            "source_type": "document",
            "source_name": row.FileName,
            "source_address": row.FileAddress,
            "title": row.Title,
            "chunk_index": row.ChunkIndex,
            "content": row.Content,
            "distance": float(row.Distance)
        })

    return results


# Search SharePoint list items

def search_list_items(
    cursor,
    embedding_json,
    top_k
):

    sql = f"""
        SELECT TOP {int(top_k)}
            ListName,
            ItemId,
            ItemAddress,
            Title,
            Content,
            Modified,

            VECTOR_DISTANCE(
                'cosine',
                Embedding,
                CAST(
                    CAST(? AS VARCHAR(MAX))
                    AS VECTOR({EMBEDDING_DIMENSIONS})
                )
            ) AS Distance

        FROM dbo.ListItems

        WHERE Embedding IS NOT NULL

        ORDER BY Distance ASC
    """

    cursor.execute(
        sql,
        embedding_json
    )

    rows = cursor.fetchall()

    results = []

    for row in rows:

        results.append({
            "source_type": "list",
            "source_name": row.ListName,
            "source_address": row.ItemAddress,
            "item_id": row.ItemId,
            "title": row.Title,
            "content": row.Content,
            "modified": row.Modified,
            "distance": float(row.Distance)
        })

    return results


# Search all indexed SharePoint content

def search(
    query,
    document_top_k=DOCUMENT_TOP_K,
    list_top_k=LIST_TOP_K
):

    # Generate query embedding

    embedding = generate_query_embedding(
        query
    )

    embedding_json = embedding_to_json(
        embedding
    )

    # Connect to SQL Server

    connection = create_sql_connection()

    cursor = connection.cursor()

    try:

        # Search document chunks

        document_results = search_document_chunks(
            cursor,
            embedding_json,
            document_top_k
        )

        # Search list items

        list_results = search_list_items(
            cursor,
            embedding_json,
            list_top_k
        )

    finally:

        cursor.close()
        connection.close()

    # Merge both result types

    results = (
        document_results
        + list_results
    )

    # Sort globally by cosine distance

    results.sort(
        key=lambda result: result["distance"]
    )

    return results

"""
# Display results (for testing)

def print_results(results):

    print()

    print("SEARCH RESULTS")

    for index, result in enumerate(
        results,
        start=1
    ):

        print()
        print(
            f"[{index}] "
            f"{result['source_type'].upper()}"
        )

        print(
            f"Title:    "
            f"{result['title']}"
        )

        print(
            f"Source:   "
            f"{result['source_name']}"
        )

        print(
            f"Distance: "
            f"{result['distance']:.4f}"
        )

        print(
            f"Address:  "
            f"{result['source_address']}"
        )

        if result["source_type"] == "document":

            print(
                f"Chunk:    "
                f"{result['chunk_index']}"
            )

        elif result["source_type"] == "list":

            print(
                f"Item ID:  "
                f"{result['item_id']}"
            )

        print()
        print(
            result["content"][:500]
        )

        print("-" * 70)


# Main

def main():

    print()

    query = input(
        "Enter your question: "
    ).strip()

    if not query:
        return

    print()
    print("Searching...")

    results = search(
        query
    )

    print_results(
        results
    )


if __name__ == "__main__":

    main()
"""