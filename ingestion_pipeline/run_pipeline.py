from s01_download_files import download_parquet, convert_to_text
from s02_populate_sp_library import upload_files
from s03_populate_sp_list import import_contacts
from s04_index_docs_sql import index_documents
from s05_index_lists_sql import index_list

def run_pipeline():

    
    print("Wikipedia RAG Data Pipeline")
    print("=" * 60)

    print("\nSTEP 1: Download Wikipedia dataset and convert it to TXT")
    download_parquet()
    convert_to_text()

    print("\nSTEP 2: Upload files to SharePoint library")
    upload_files()

    print("\nSTEP 3: Create items in SharePoint list")
    import_contacts

    print("\nSTEP 4: Index SharePoint documents")
    index_documents()

    print("\nSTEP 5: Index SharePoint list items")
    index_list()

    print()
    print("Pipeline completed.")

if __name__ == "__run_pipeline__":
    run_pipeline()