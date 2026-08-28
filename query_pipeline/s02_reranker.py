import os
import requests

from dotenv import load_dotenv


load_dotenv()


# Configuration

API_URL = os.getenv("API_URL")
RERANKER_MODEL = os.getenv("RERANKER_MODEL")
DEFAULT_TOP_K = int(os.getenv("DEFAULT_TOP_K"))


# Get API key

def get_api_key():

    api_key = os.getenv("API_KEY")

    return api_key


# Rerank search results

def rerank(
    query,
    results,
    top_k=DEFAULT_TOP_K
):

    if not results:
        return []

    api_key = get_api_key()

    # Extract content from search results

    documents = [
        result["content"]
        for result in results
    ]

    # Prepare API request

    url = (
        f"{API_URL.rstrip('/')}"
        f"/rerank"
    )

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": RERANKER_MODEL,
        "query": query,
        "documents": documents,
        "top_n": min(
            top_k,
            len(documents)
        )
    }

    # Call reranker API

    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=60
    )

    if not response.ok:

        print()
        print("Reranker API error:")
        print(
            f"HTTP {response.status_code}"
        )
        print(response.text)

    response.raise_for_status()

    data = response.json()

    # Read reranker results

    reranker_results = data.get(
        "results",
        []
    )

    # Map reranked indexes back to original search results

    final_results = []

    for reranked in reranker_results:

        original_index = reranked[
            "index"
        ]

        relevance_score = reranked.get(
            "relevance_score",
            0
        )

        result = results[
            original_index
        ].copy()

        result[
            "rerank_score"
        ] = float(
            relevance_score
        )

        final_results.append(
            result
        )

    # Sort highest relevance first

    final_results.sort(
        key=lambda result:
            result["rerank_score"],
        reverse=True
    )

    return final_results

"""
# Display results (for testing)

def print_results(results):

    print()

    print("RERANKED RESULTS")

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
            f"Title:        "
            f"{result['title']}"
        )

        print(
            f"Source:       "
            f"{result['source_name']}"
        )

        print(
            f"Vector dist.: "
            f"{result['distance']:.4f}"
        )

        print(
            f"Rerank score: "
            f"{result['rerank_score']:.4f}"
        )

        print(
            f"Address:      "
            f"{result['source_address']}"
        )

        print()

        print(
            result["content"][:500]
        )

        print("-" * 70)


# Main

def main():

    from s01_search import search

    print()

    query = input(
        "Enter your question: "
    ).strip()

    if not query:
        return

    # Stage 1: Vector search

    print()
    print("Searching...")

    results = search(
        query
    )

    print(
        f"Search returned "
        f"{len(results)} candidates."
    )

    # Stage 2: Reranking

    print("Reranking...")

    results = rerank(
        query,
        results
    )

    print_results(
        results
    )


if __name__ == "__main__":

    main()
"""