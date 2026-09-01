import os
import json
import requests
import pyodbc

from dotenv import load_dotenv
from requests_ntlm import HttpNtlmAuth
from sentence_transformers import SentenceTransformer


load_dotenv()


# SharePoint configuration

SHAREPOINT_URL = os.getenv("SHAREPOINT_URL")
SHAREPOINT_USERNAME = os.getenv("SHAREPOINT_USERNAME")
SHAREPOINT_PASSWORD = os.getenv("SHAREPOINT_PASSWORD")

SHAREPOINT_LIST = "Contacts"


# SQL Server configuration

SQL_SERVER = os.getenv("SQL_SERVER")
SQL_DATABASE = os.getenv("SQL_DATABASE")
SQL_USERNAME = os.getenv("SQL_USERNAME")
SQL_PASSWORD = os.getenv("SQL_PASSWORD")

SQL_CONNECTION_STRING = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    f"SERVER={SQL_SERVER};"
    f"DATABASE={SQL_DATABASE};"
    f"UID={SQL_USERNAME};"
    f"PWD={SQL_PASSWORD};"
    "TrustServerCertificate=yes;"
)


# Embedding configuration

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL")

EMBEDDING_DIMENSIONS = int(os.getenv("EMBEDDING_DIMENSIONS"))



# SharePoint system fields (excluded)

SYSTEM_FIELDS = {
    "__metadata",
    "Id",
    "ID",
    "Title",
    "Modified",
    "Created",
    "AuthorId",
    "EditorId",
    "Attachments",
    "GUID",
    "FileSystemObjectType",
    "ContentTypeId",
    "OData__UIVersionString",
    "owshiddenversion"
}


# Load embedding model

print("Loading embedding model...")

model = SentenceTransformer(EMBEDDING_MODEL)

print("Embedding model loaded.")


# Create SharePoint session

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


# Get SharePoint field definitions

def get_field_definitions(session):

    url = (
        f"{SHAREPOINT_URL}"
        f"/_api/web/lists/"
        f"getbytitle('{SHAREPOINT_LIST}')"
        f"/fields"
        f"?$select="
        f"Title,"
        f"InternalName,"
        f"Hidden,"
        f"ReadOnlyField"
    )

    response = session.get(url)

    if not response.ok:

        print("Could not retrieve list fields.")
        print(response.text)

    response.raise_for_status()

    fields = response.json()[
        "d"
    ][
        "results"
    ]

    field_map = {}

    for field in fields:

        internal_name = field.get(
            "InternalName"
        )

        display_name = field.get(
            "Title"
        )

        hidden = field.get(
            "Hidden",
            False
        )

        if not internal_name:
            continue

        if not display_name:
            continue

        if hidden:
            continue

        field_map[
            internal_name
        ] = display_name

    return field_map


# Get SharePoint list items

def get_sharepoint_items(session):

    url = (
        f"{SHAREPOINT_URL}"
        f"/_api/web/lists/"
        f"getbytitle('{SHAREPOINT_LIST}')"
        f"/items"
    )

    items = []

    while url:

        response = session.get(url)

        if not response.ok:

            print(
                "Could not retrieve "
                "SharePoint list items."
            )

            print(response.text)

        response.raise_for_status()

        data = response.json()["d"]

        items.extend(
            data["results"]
        )

        # SharePoint REST pagination
        url = data.get("__next")

    return items


# Convert SharePoint field value to text

def value_to_text(value):

    if value is None:
        return ""

    # Boolean

    if isinstance(value, bool):

        return (
            "Yes"
            if value
            else "No"
        )

    # Simple values

    if isinstance(
        value,
        (str, int, float)
    ):

        return str(value).strip()

    # SharePoint object (like lookup fields)

    if isinstance(value, dict):

        preferred_keys = [
            "Title",
            "Value",
            "Name",
            "LookupValue",
            "Email"
        ]

        for key in preferred_keys:

            if key in value:

                result = value.get(key)

                if result:

                    return str(
                        result
                    ).strip()

        return ""

    # Multi-value fields

    if isinstance(value, list):

        values = []

        for entry in value:

            text = value_to_text(
                entry
            )

            if text:
                values.append(text)

        return ", ".join(values)

    return str(value).strip()


# Build semantic content

def build_item_content(
    item,
    field_map
):

    lines = []

    for internal_name, value in item.items():

        # Ignore SharePoint system fields
        if internal_name in SYSTEM_FIELDS:
            continue

        # Only use fields that exist in the SharePoint field definitions
        if internal_name not in field_map:
            continue

        text_value = value_to_text(
            value
        )

        if not text_value:
            continue

        display_name = field_map[
            internal_name
        ]

        lines.append(
            f"{display_name}: "
            f"{text_value}"
        )

    return "\n".join(lines)


# Get item title

def get_item_title(item):

    title = value_to_text(
        item.get("Title")
    )

    if title:
        return title

    item_id = item.get(
        "Id",
        item.get("ID")
    )

    return f"Item {item_id}"


# Build SharePoint item URL

def get_item_address(item_id):

    return (
        f"{SHAREPOINT_URL.rstrip('/')}"
        f"/Lists/{SHAREPOINT_LIST}/"
        f"DispForm.aspx?ID={item_id}"
    )


# Generate embedding

def generate_embedding(content):

    embedding = model.encode(
        content,
        normalize_embeddings=True,
        show_progress_bar=False
    )

    return embedding


# SQL connection

def create_sql_connection():

    return pyodbc.connect(
        SQL_CONNECTION_STRING
    )


# Delete existing list item

def delete_existing_item(
    cursor,
    list_name,
    item_id
):

    cursor.execute(
        """
        DELETE FROM dbo.ListItems
        WHERE ListName = ?
          AND ItemId = ?
        """,
        list_name,
        item_id
    )


# Insert list item

def insert_item(
    cursor,
    item_id,
    item_address,
    title,
    content,
    embedding,
    modified
):

    embedding_json = json.dumps(
        embedding.tolist()
    )

    sql = f"""
        INSERT INTO dbo.ListItems
        (
            ListName,
            ItemId,
            ItemAddress,
            Title,
            Content,
            Embedding,
            Modified
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
            ),
            ?
        )
    """

    cursor.execute(
        sql,
        SHAREPOINT_LIST,
        item_id,
        item_address,
        title,
        content,
        embedding_json,
        modified
    )


# Process one SharePoint item

def process_item(
    cursor,
    item,
    field_map
):

    item_id = item.get(
        "Id",
        item.get("ID")
    )

    if item_id is None:

        raise RuntimeError("SharePoint item has no ID.")

    title = get_item_title(item)

    item_address = get_item_address(item_id)

    modified = item.get("Modified")

    print()

    print(f"Processing item: {item_id}")

    print(f"Title:           {title}")

    print(f"Address:         {item_address}")

    # Build semantic content dynamically

    content = build_item_content(
        item,
        field_map
    )

    if not content:

        raise RuntimeError(
            "List item contains "
            "no indexable content."
        )

    print()
    print("Content:")
    print(content)

    # Generate embedding

    embedding = generate_embedding(
        content
    )

    print()

    print(
        f"Embedding:       "
        f"{len(embedding)} dimensions"
    )

    # Delete previous version

    delete_existing_item(
        cursor,
        SHAREPOINT_LIST,
        item_id
    )

    # Insert current version

    insert_item(
        cursor,
        item_id,
        item_address,
        title,
        content,
        embedding,
        modified
    )

    print(
        "Indexed successfully."
    )


# Main indexing process

def index_list():

    # SharePoint

    print()
    print("Connecting to SharePoint...")

    sp_session = create_sharepoint_session()

    # Get field definitions

    print(
        f"Reading fields from "
        f"'{SHAREPOINT_LIST}'..."
    )

    field_map = get_field_definitions(sp_session)

    print(
        f"Found {len(field_map)} "
        f"usable fields."
    )

    # Get list items

    items = get_sharepoint_items(
        sp_session
    )

    print(
        f"Found {len(items)} items "
        f"in '{SHAREPOINT_LIST}'."
    )

    # SQL Server

    print()
    print("Connecting to SQL Server...")

    sql_connection = (create_sql_connection())

    cursor = (sql_connection.cursor())

    print("Connected to SQL Server.")

    # Process items

    successful = 0
    failed = 0

    for item in items:

        try:

            process_item(
                cursor,
                item,
                field_map
            )

            # Commit each item separately
            sql_connection.commit()

            successful += 1

        except Exception as e:

            sql_connection.rollback()

            failed += 1

            item_id = item.get(
                "Id",
                item.get(
                    "ID",
                    "Unknown"
                )
            )

            print(
                f"FAILED: item {item_id}"
            )

            print(e)

    # Close SQL connection

    cursor.close()

    sql_connection.close()

    # Summary

    print()
    print("LIST INDEXING COMPLETED")

    print(
        f"List:          "
        f"{SHAREPOINT_LIST}"
    )

    print(
        f"Items indexed: "
        f"{successful}"
    )

    print(
        f"Items failed:  "
        f"{failed}"
    )


# Main

def main():

    index_list()

if __name__ == "__main__":

    main()