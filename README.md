# SharePoint RAG

A Retrieval-Augmented Generation (RAG) solution for **SharePoint Server** that indexes documents and SharePoint list items into **SQL Server vector storage**, retrieves relevant content using semantic search, reranks the results, and generates answers using an LLM.

The project is designed primarily for **on-premises SharePoint environments using NTLM authentication**.

## Architecture

```text
                     SharePoint Server
                     On-Premises / NTLM
                            |
                 +----------+----------+
                 |                     |
                 v                     v
        Document Libraries       SharePoint Lists
                 |                     |
                 v                     v
          Document Content         List Items
                 |                     |
                 +----------+----------+
                            |
                            v
                   Text Representation
                            |
                            v
                    BGE Embeddings
                            |
                            v
                  SQL Server VECTOR
                            |
                            v
                    Vector Retrieval
                            |
                            v
                       Reranker
                            |
                            v
                           LLM
                            |
                            v
                     Streamlit UI
```



## Features

- Connects to on-premises SharePoint using NTLM authentication
- Downloads and processes SharePoint document-library content
- Reads SharePoint list items through the REST API
- Supports generic SharePoint list indexing without hard-coded list columns
- Uses SharePoint display names when representing list fields
- Generates semantic embeddings using `BAAI/bge-small-en-v1.5`
- Stores 384-dimensional embeddings using SQL Server `VECTOR`
- Searches both document chunks and SharePoint list items
- Uses cosine vector distance for initial retrieval
- Reranks retrieved candidates before answer generation
- Generates answers based on retrieved SharePoint context
- Preserves links to original SharePoint documents and list items
- Provides a conversational Streamlit interface



## RAG Pipeline

The query pipeline consists of three stages:

```text
User Question
     |
     v
+--------------------+
|  Vector Retrieval  |
|   s01_search.py    |
+---------+----------+
          |
          | Candidate results
          v
+--------------------+
|      Reranker      |
| s02_reranker.py    |
+---------+----------+
          |
          | Most relevant results
          v
+--------------------+
| Answer Generation  |
|s03_generate_answer |
+---------+----------+
          |
          v
   Answer + Sources
```



### 1. Vector Search

The user's question is embedded using the same embedding model used during indexing.

The resulting vector is compared against embeddings stored in:

- `dbo.DocumentChunks`
- `dbo.ListItems`

Candidates from both sources are returned and combined.

### 2. Reranking

Initial vector retrieval is optimized for recall.

The candidate results are then reranked against the original question using a dedicated reranking model.

Current configuration:

```text
cohere-rerank-v4.0-fast
```



### 3. Answer Generation

The highest-ranked SharePoint content is passed to the LLM together with the user's question.

The LLM is instructed to answer from the retrieved SharePoint context and reference the provided sources.

## Project Structure

```text
SharepointRAG/
|
+-- app/
|   +-- app.py
|
+-- pipeline/
|   +-- 01_download_files.py
|   +-- 02_populate_sp_library.py
|   +-- 03_populate_sp_list.py
|   +-- 04_index_docs_sql.py
|   +-- 05_index_lists_sql.py
|
+-- query_pipeline/
|   +-- s01_search.py
|   +-- s02_reranker.py
|   +-- s03_generate_answer.py
|
+-- downloads/
|
+-- .env
+-- .env.example
+-- .gitignore
+-- requirements.txt
+-- README.md
```



## Indexing Pipeline

The indexing scripts are numbered according to their intended execution order.

### `01_download_files.py`

Downloads source/test documents used for populating the SharePoint environment.

### `02_populate_sp_library.py`

Uploads documents to a SharePoint document library using NTLM authentication and the SharePoint REST API.

### `03_populate_sp_list.py`

Populates a SharePoint list with test records.

### `04_index_docs_sql.py`

Reads documents from the SharePoint library, splits their content into chunks, generates embeddings, and stores the chunks in SQL Server.

Conceptually:

```text
SharePoint Document
        |
        v
    Extract Text
        |
        v
 Sentence Chunking
        |
        v
 BGE Embeddings
        |
        v
dbo.DocumentChunks
```



### `05_index_lists_sql.py`

Reads items from a SharePoint list and creates one semantic representation per item.

List schemas are discovered dynamically. SharePoint internal field names are mapped to their display names before content is embedded.

For example:

```text
First Name: Jonas
E-mail Address: jonas@example.test
Company: Northstar Technologies
Job Title: IT Manager
City: Berlin
Country/Region: Germany
```

is converted into one embedding and stored in `dbo.ListItems`.

This allows the indexer to work with different SharePoint list schemas without requiring every business field to have its own SQL column.

## SQL Server

The solution uses SQL Server's vector data type for embedding storage.

### Document Chunks

A document can produce multiple vector records.

Example structure:

```sql
CREATE TABLE dbo.DocumentChunks
(
    Id BIGINT IDENTITY(1,1) PRIMARY KEY,
    FileName NVARCHAR(500),
    FileAddress NVARCHAR(1000),
    Title NVARCHAR(500),
    ChunkIndex INT,
    Content NVARCHAR(MAX),
    Embedding VECTOR(384)
);
```

`FileAddress` stores the URL of the original SharePoint document so applications can link search results back to SharePoint.

### SharePoint List Items

A normal SharePoint list item is treated as one semantic unit rather than being chunked.

Example structure:

```sql
CREATE TABLE dbo.ListItems
(
    Id BIGINT IDENTITY(1,1) PRIMARY KEY,
    ListName NVARCHAR(255) NOT NULL,
    ItemId INT NOT NULL,
    ItemAddress NVARCHAR(1000),
    Title NVARCHAR(500),
    Content NVARCHAR(MAX),
    Embedding VECTOR(384),
    Modified DATETIME2
);
```

A unique index can be used to identify each SharePoint item:

```sql
CREATE UNIQUE INDEX UX_ListItems_ListName_ItemId
ON dbo.ListItems(ListName, ItemId);
```



## Embedding Model

The current embedding model is:

```text
BAAI/bge-small-en-v1.5
```

Embedding dimensions:

```text
384
```

Embeddings are normalized before being stored.

The same model must be used for both:

- indexing SharePoint content
- embedding user queries



## Configuration

Create a `.env` file in the project root.

Example:

```env
# SharePoint

SHAREPOINT_URL=http://your-sharepoint-server
SHAREPOINT_USERNAME=DOMAIN\service-account
SHAREPOINT_PASSWORD=your-password

# SQL Server

SQL_SERVER=your-sql-server
SQL_DATABASE=your-database

# Embeddings

EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
EMBEDDING_DIMENSIONS=384

MAX_CHUNK_TOKENS=512
OVERLAP_TOKENS=80

# Reranker API

API_URL=https://your-provider.example/v1
API_KEY=your-api-key

RERANKER_MODEL=cohere-rerank-v4.0-fast
DEFAULT_TOP_K=5

# LLM

LLM_MODEL=your-llm-model
```



## Installation

Create a Python virtual environment:

```bash
python -m venv .venv
```

Activate it on Windows:

```bash
.venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Core dependencies include:

```text
requests
requests-ntlm
python-dotenv
pyodbc
sentence-transformers
nltk
streamlit
```

SQL Server access also requires:

```text
ODBC Driver 18 for SQL Server
```



## Running the Indexing Pipeline

Run the indexing scripts from the project root in sequence:

```bash
python pipeline/01_download_files.py
python pipeline/02_populate_sp_library.py
python pipeline/03_populate_sp_list.py
python pipeline/04_index_docs_sql.py
python pipeline/05_index_lists_sql.py
```

The first three scripts are primarily useful for creating/populating a test environment. Existing SharePoint environments can skip those steps as appropriate.

## Testing Vector Search

The search module can be run independently:

```bash
python query_pipeline/s01_search.py
```

It searches both document chunks and SharePoint list items.

## Testing Reranking

Run:

```bash
python query_pipeline/s02_reranker.py
```

The module performs vector retrieval first and then reranks the returned candidates.

## Testing the Complete RAG Pipeline

Run:

```bash
python query_pipeline/s03_generate_answer.py
```

This executes:

```text
Search
  |
  v
Rerank
  |
  v
Generate Answer
```



## Running the Streamlit Application

From the project root:

```bash
python -m streamlit run app/app.py
```

Then open the local Streamlit address displayed in the terminal.

The application provides a chat interface and runs:

```text
Question
   |
   v
SQL Vector Search
   |
   v
Reranking
   |
   v
LLM
   |
   v
Answer
   |
   +--> SharePoint Sources
```



## Source Traceability

Search results retain metadata pointing to their original SharePoint source.

Documents contain information such as:

```text
Source Type
File Name
Title
Chunk Index
SharePoint File URL
```

List items contain:

```text
Source Type
List Name
Item ID
Title
SharePoint Item URL
```

This allows the UI to provide links back to the original SharePoint content instead of treating the vector database as the authoritative source.

## Security

This project handles credentials for SharePoint, SQL Server, and external AI APIs.

Never commit:

- `.env`
- SharePoint passwords
- API keys
- access tokens
- production data
- downloaded confidential SharePoint documents

Recommended `.gitignore` entries:

```gitignore
.env
.env.*
!.env.example

.venv/
venv/
__pycache__/
*.py[cod]

downloads/

.ipynb_checkpoints/
.vscode/
.idea/

*.log
.DS_Store
Thumbs.db
```

For production environments, consider using a dedicated SharePoint service account with only the permissions required to read the content being indexed.

## Current Limitations

The current implementation is intentionally focused on establishing a clear end-to-end RAG pipeline.

Current limitations include:

- document ingestion is primarily focused on plain-text content
- Word/PDF extraction is not yet part of the core pipeline
- list indexing currently targets one configured SharePoint list per run
- SharePoint permissions are not yet propagated to individual vector records
- indexing currently performs straightforward reindexing rather than a complete incremental synchronization strategy



## Potential Improvements

Possible future enhancements include:

- DOCX extraction
- PDF extraction
- PowerPoint and Excel extraction
- incremental SharePoint synchronization
- indexing multiple SharePoint lists
- deletion detection
- SharePoint permission/ACL-aware retrieval
- metadata filtering
- hybrid keyword + vector search
- improved citation rendering
- configurable retrieval strategies
- conversation history
- streaming LLM responses
- Teams integration
- centralized pipeline orchestration
- scheduled reindexing
- evaluation datasets and RAG quality metrics



## Why Rerank?

Vector similarity is useful for quickly retrieving semantically related candidates, but the nearest vectors are not necessarily the best context for answering a specific question.

This project therefore uses a two-stage retrieval architecture:

```text
Large Search Space
       |
       v
Fast Vector Retrieval
       |
   Candidates
       |
       v
More Accurate Reranker
       |
 Best Context
       |
       v
      LLM
```

This provides a useful balance between retrieval speed and relevance.

## License

The MIT and Apache 2.0 licenses.