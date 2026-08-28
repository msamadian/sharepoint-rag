import os
import csv
import requests

from dotenv import load_dotenv
from requests_ntlm import HttpNtlmAuth


load_dotenv()


# Project paths

BASE_DIR = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

DOWNLOAD_FOLDER = os.path.join(
    BASE_DIR,
    "downloads"
)

CSV_FILE = os.path.join(
    DOWNLOAD_FOLDER,
    "synthetic_contacts.csv"
)


# SharePoint configuration

SHAREPOINT_URL = os.getenv("SHAREPOINT_URL")
SHAREPOINT_USERNAME = os.getenv("SHAREPOINT_USERNAME")
SHAREPOINT_PASSWORD = os.getenv("SHAREPOINT_PASSWORD")

SHAREPOINT_LIST = "Contacts"


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


# Check Contacts list

def check_list(session):

    url = (
        f"{SHAREPOINT_URL}"
        f"/_api/web/lists/getbytitle('{SHAREPOINT_LIST}')"
        f"?$select=Title,ItemCount"
    )

    response = session.get(url)

    response.raise_for_status()

    data = response.json()["d"]

    print(f"List: {data['Title']}")
    print(f"Existing items: {data['ItemCount']}")
    print()


# Get request digest

def get_request_digest(session):

    url = (
        f"{SHAREPOINT_URL}"
        f"/_api/contextinfo"
    )

    response = session.post(url)

    response.raise_for_status()

    data = response.json()

    return (
        data["d"]
        ["GetContextWebInformation"]
        ["FormDigestValue"]
    )


# Get list item entity type

def get_list_item_type(session):

    url = (
        f"{SHAREPOINT_URL}"
        f"/_api/web/lists/getbytitle('{SHAREPOINT_LIST}')"
        f"?$select=ListItemEntityTypeFullName"
    )

    response = session.get(url)

    response.raise_for_status()

    return response.json()["d"][
        "ListItemEntityTypeFullName"
    ]


# Create a contact

def create_contact(
    session,
    digest,
    item_type,
    row
):

    url = (
        f"{SHAREPOINT_URL}"
        f"/_api/web/lists/getbytitle('{SHAREPOINT_LIST}')"
        f"/items"
    )

    payload = {

        "__metadata": {
            "type": item_type
        },

        "FirstName": row["FirstName"],
        "Title": row["Title"],
        "Email": row["Email"],
        "CellPhone": row["CellPhone"],
        "Company": row["Company"],
        "JobTitle": row["JobTitle"],
        "WorkAddress": row["WorkAddress"],
        "WorkCity": row["WorkCity"],
        "WorkState": row["WorkState"],
        "WorkZip": row["WorkZip"],
        "WorkCountry": row["WorkCountry"]
    }

    headers = {
        "Accept": "application/json;odata=verbose",
        "Content-Type": "application/json;odata=verbose",
        "X-RequestDigest": digest
    }

    response = session.post(
        url,
        json=payload,
        headers=headers
    )

    if response.ok:
        return True

    print()
    print("ERROR creating contact:")
    print(
        f"{row['FirstName']} "
        f"{row['Title']}"
    )

    print(
        f"HTTP Status: {response.status_code}"
    )

    print(
        f"Response: {response.text}"
    )

    return False


# Import contacts

def import_contacts():

    session = create_sharepoint_session()

    check_list(session)

    item_type = get_list_item_type(session)

    print(f"List item type: {item_type}")

    digest = get_request_digest(session)

    print("Request digest received.")
    print()

    # Read CSV

    success = 0
    failed = 0

    print("Starting import...")
    print("-" * 60)

    with open(
        CSV_FILE,
        mode="r",
        encoding="utf-8-sig",
        newline=""
    ) as csv_file:

        reader = csv.DictReader(
            csv_file,
            delimiter=";"
        )

        for index, row in enumerate(
            reader,
            start=1
        ):

            full_name = (
                f"{row['FirstName']} "
                f"{row['Title']}"
            )

            print(
                f"[{index:03}] "
                f"{full_name:<30}",
                end=" "
            )

            try:

                result = create_contact(
                    session,
                    digest,
                    item_type,
                    row
                )

                if result:

                    success += 1
                    print("OK")

                else:

                    failed += 1
                    print("FAILED")

            except Exception as error:

                failed += 1

                print("ERROR")
                print(f"    {error}")


    # Summary

    print()
    print(f"Successful: {success}")
    print(f"Failed:     {failed}")


# Main

if __name__ == "__main__":

    import_contacts()