import os
import requests

from dotenv import load_dotenv


load_dotenv()


# Configuration

API_URL = os.getenv("API_URL")
LLM_MODEL = os.getenv("LLM_MODEL")


# Get API key

def get_api_key():

    api_key = os.getenv("API_KEY")

    return api_key


# Build context from reranked results

def build_context(results):

    context_parts = []

    for index, result in enumerate(
        results,
        start=1
    ):

        source_type = result.get(
            "source_type",
            "unknown"
        )

        title = result.get(
            "title",
            ""
        )

        source_name = result.get(
            "source_name",
            ""
        )

        source_address = result.get(
            "source_address",
            ""
        )

        content = result.get(
            "content",
            ""
        )

        context = (
            f"[Source {index}]\n"
            f"Type: {source_type}\n"
            f"Title: {title}\n"
            f"Source: {source_name}\n"
            f"Address: {source_address}\n"
            f"Content:\n{content}"
        )

        context_parts.append(
            context
        )

    return "\n\n".join(
        context_parts
    )


# Generate answer

def generate_answer(
    query,
    results
):

    if not results:

        return (
            "I could not find relevant information in the indexed SharePoint content."
        )

    api_key = get_api_key()

    context = build_context(
        results
    )

    # System prompt

    system_prompt = """
You are an assistant that answers questions using information
retrieved from a SharePoint knowledge base.

Use only the provided context to answer the user's question.

Rules:

1. Base your answer only on the provided SharePoint context.

2. Do not invent information that is not supported by the context.

3. If the context does not contain enough information to answer
   the question, clearly say that the available SharePoint content
   does not provide enough information.

4. Combine information from multiple sources when useful.

5. When sources disagree, mention the disagreement rather than
   choosing one without evidence.

6. Answer naturally and directly.

7. Cite sources using [Source 1], [Source 2], etc.

8. Do not expose or discuss vector distances, embedding scores,
   reranking scores, or internal retrieval details.
""".strip()

    # User prompt

    user_prompt = f"""
Question:

{query}


SharePoint context:

{context}


Answer the question using the SharePoint context above.
""".strip()

    # API request

    url = (
        f"{API_URL.rstrip('/')}"
        f"/chat/completions"
    )

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": LLM_MODEL,

        "messages": [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": user_prompt
            }
        ],

        "temperature": 0.2
    }

    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=120
    )

    if not response.ok:

        print()
        print("LLM API error:")
        print(
            f"HTTP {response.status_code}"
        )
        print(response.text)

    response.raise_for_status()

    data = response.json()

    answer = (
        data["choices"][0]
        ["message"]
        ["content"]
    )

    return answer.strip()


# Display sources

def print_sources(results):

    print()
    print("SOURCES")

    for index, result in enumerate(
        results,
        start=1
    ):

        print()

        print(
            f"[Source {index}] "
            f"{result.get('title', '')}"
        )

        print(
            f"Type:    "
            f"{result.get('source_type', '')}"
        )

        print(
            f"Source:  "
            f"{result.get('source_name', '')}"
        )

        print(
            f"Address: "
            f"{result.get('source_address', '')}"
        )


# Main

def main():

    from s01_search import search
    from s02_reranker import rerank

    print()

    query = input(
        "Enter your question: "
    ).strip()

    if not query:
        return

    # Stage 1: Vector search

    print()
    print("Searching...")

    search_results = search(
        query
    )

    print(
        f"Found {len(search_results)} "
        f"candidates."
    )

    # Stage 2: Reranking

    print(
        "Reranking..."
    )

    reranked_results = rerank(
        query,
        search_results
    )

    print(
        f"Using {len(reranked_results)} "
        f"sources."
    )

    # Stage 3: Generate answer

    print(
        "Generating answer..."
    )

    answer = generate_answer(
        query,
        reranked_results
    )

    # Display answer

    print()
    print("ANSWER")
    print()
    print(answer)

    # Display sources

    print_sources(
        reranked_results
    )


if __name__ == "__main__":

    main()