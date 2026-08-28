import os
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

OUTPUT_FOLDER = os.path.join(
    DOWNLOAD_FOLDER,
    "text_files"
)


# SharePoint configuration

SHAREPOINT_URL = os.getenv("SHAREPOINT_URL")
SHAREPOINT_USERNAME = os.getenv("SHAREPOINT_USERNAME")
SHAREPOINT_PASSWORD = os.getenv("SHAREPOINT_PASSWORD")

SHAREPOINT_FOLDER = "/Docs"

MAX_UPLOADS = 120


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


# Get SharePoint request digest

def get_request_digest(session):

    url = f"{SHAREPOINT_URL}/_api/contextinfo"

    response = session.post(
        url,
        headers={
            "Accept": "application/json;odata=verbose"
        }
    )

    response.raise_for_status()

    data = response.json()

    digest = data[
        "d"
    ][
        "GetContextWebInformation"
    ][
        "FormDigestValue"
    ]

    return digest


# Upload single file

def upload_file_to_sharepoint(
    session,
    digest,
    local_file
):

    filename = os.path.basename(local_file)

    safe_filename = filename.replace(
        "'",
        "''"
    )

    safe_folder = SHAREPOINT_FOLDER.replace(
        "'",
        "''"
    )

    url = (
        f"{SHAREPOINT_URL}"
        f"/_api/web/"
        f"GetFolderByServerRelativeUrl('{safe_folder}')"
        f"/Files/add("
        f"url='{safe_filename}',"
        f"overwrite=true)"
    )

    with open(local_file, "rb") as file:
        content = file.read()

    response = session.post(
        url,
        headers={
            "Accept": "application/json;odata=verbose",
            "Content-Type": "text/plain; charset=utf-8",
            "X-RequestDigest": digest
        },
        data=content
    )

    response.raise_for_status()

    return True


# Upload all files

def upload_files():

    print("\nConnecting to SharePoint...")

    try:
        session = create_sharepoint_session()
        digest = get_request_digest(session)

    except Exception as e:

        print("Could not connect to SharePoint.")
        print(e)

        return

    print("Connected to SharePoint.")
    print(f"Target: {SHAREPOINT_FOLDER}")
    print()

    files = [
        filename
        for filename in os.listdir(OUTPUT_FOLDER)
    ]

    files.sort()

    print(f"Found {len(files)} files.")
    print()

    uploaded = 0
    failed = 0

    for filename in files:

        if uploaded >= MAX_UPLOADS:
            break

        filepath = os.path.join(
            OUTPUT_FOLDER,
            filename
        )

        try:

            upload_file_to_sharepoint(
                session,
                digest,
                filepath
            )

            uploaded += 1

            print(
                f"[{uploaded}/{len(files)}] "
                f"Uploaded: {filename}"
            )

        except Exception as e:

            failed += 1

            print(
                f"FAILED: {filename}"
            )

            print(e)

    print()
    print("----------------------------")
    print("Upload completed")
    print(f"Uploaded: {uploaded}")
    print(f"Failed:   {failed}")
    print("----------------------------")


# Main

def main():

    upload_files()


if __name__ == "__main__":
    main()