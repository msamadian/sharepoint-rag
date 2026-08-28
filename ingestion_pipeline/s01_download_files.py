import os
import re
import requests
import pyarrow.parquet as pq

from tqdm import tqdm

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

PARQUET_FILE = os.path.join(
    DOWNLOAD_FOLDER,
    "wikipedia.parquet"
)


# Configuration

PARQUET_URL = (
    "https://huggingface.co/datasets/wikimedia/wikipedia/resolve/main/20231101.en/train-00000-of-00041.parquet"
)

MAX_ARTICLES = 100



# Download Parquet

def download_parquet():

    os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

    if os.path.exists(PARQUET_FILE):
        print("Parquet file already exists. Skipping download.")
        return

    print("Downloading Wikipedia Parquet...")

    with requests.get(PARQUET_URL, stream=True) as response:

        response.raise_for_status()

        total_size = int(
            response.headers.get("content-length", 0)
        )

        with open(PARQUET_FILE, "wb") as file:

            with tqdm(
                total=total_size,
                unit="B",
                unit_scale=True,
                desc="Downloading"
            ) as progress:

                for chunk in response.iter_content(
                    chunk_size=1024 * 1024
                ):
                    if chunk:
                        file.write(chunk)
                        progress.update(len(chunk))

    print("Download completed.")


# Convert Wikipedia articles

def convert_to_text():

    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    print("\nOpening Parquet file...")

    parquet = pq.ParquetFile(PARQUET_FILE)

    print("Columns:")
    print(parquet.schema.names)

    article_number = 1

    for batch in parquet.iter_batches(
        batch_size=1000
    ):

        rows = batch.to_pylist()

        for row in rows:

            if article_number > MAX_ARTICLES:

                print(
                    f"\nFinished. Created "
                    f"{article_number} text files."
                )

                return

            title = row.get("title")
            text = row.get("text")

            if not title or not text:
                continue

            filename = (
                f"{article_number:03d} {title}.txt"
            )

            filepath = os.path.join(
                OUTPUT_FOLDER,
                filename
            )

            content = (
                f"Title: {title}\n\n"
                f"{text}"
            )

            with open(
                filepath,
                "w",
                encoding="utf-8"
            ) as file:

                file.write(content)

            print(
                f"[{article_number}/{MAX_ARTICLES}] "
                f"{title}"
            )

            article_number += 1


# Main

def main():

    download_parquet()

    convert_to_text()


if __name__ == "__main__":
    main()