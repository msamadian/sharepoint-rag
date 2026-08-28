import os
import sys

import streamlit as st


# --------------------------------------------------
# Project paths
# --------------------------------------------------

BASE_DIR = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

if BASE_DIR not in sys.path:
    sys.path.insert(
        0,
        BASE_DIR
    )


# --------------------------------------------------
# Import query pipeline
# --------------------------------------------------

from query_pipeline.s01_search import search
from query_pipeline.s02_reranker import rerank
from query_pipeline.s03_generate_answer import generate_answer


# --------------------------------------------------
# Page configuration
# --------------------------------------------------

st.set_page_config(
    page_title="SharePoint RAG",
    page_icon="🔎",
    layout="wide"
)


# --------------------------------------------------
# Helper: initialize session
# --------------------------------------------------

def initialize_session():

    if "messages" not in st.session_state:
        st.session_state.messages = []


# --------------------------------------------------
# Helper: display sources
# --------------------------------------------------

def display_sources(results):

    if not results:
        return

    with st.expander(
        f"Sources ({len(results)})"
    ):

        for index, result in enumerate(
            results,
            start=1
        ):

            title = result.get(
                "title",
                "Untitled"
            )

            source_type = result.get(
                "source_type",
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

            rerank_score = result.get(
                "rerank_score"
            )

            st.markdown(
                f"**[{index}] {title}**"
            )

            if source_type:
                st.caption(
                    f"{source_type.title()} · "
                    f"{source_name}"
                )

            if source_address:

                st.markdown(
                    f"[Open in SharePoint]"
                    f"({source_address})"
                )

            if rerank_score is not None:

                st.caption(
                    f"Relevance: "
                    f"{rerank_score:.4f}"
                )

            if index < len(results):
                st.divider()


# --------------------------------------------------
# Helper: process question
# --------------------------------------------------

def ask(question):

    # --------------------------------------------------
    # 1. Vector search
    # --------------------------------------------------

    with st.status(
        "Searching SharePoint...",
        expanded=False
    ) as status:

        search_results = search(
            question
        )

        status.update(
            label=(
                f"Found "
                f"{len(search_results)} candidates"
            ),
            state="complete"
        )

    if not search_results:

        return (
            "I couldn't find relevant information "
            "in the indexed SharePoint content.",
            []
        )

    # --------------------------------------------------
    # 2. Reranking
    # --------------------------------------------------

    with st.status(
        "Reranking results...",
        expanded=False
    ) as status:

        reranked_results = rerank(
            question,
            search_results
        )

        status.update(
            label=(
                f"Selected "
                f"{len(reranked_results)} sources"
            ),
            state="complete"
        )

    if not reranked_results:

        return (
            "I couldn't find sufficiently relevant "
            "SharePoint content for this question.",
            []
        )

    # --------------------------------------------------
    # 3. Generate answer
    # --------------------------------------------------

    with st.status(
        "Generating answer...",
        expanded=False
    ) as status:

        answer = generate_answer(
            question,
            reranked_results
        )

        status.update(
            label="Answer generated",
            state="complete"
        )

    return (
        answer,
        reranked_results
    )


# --------------------------------------------------
# Initialize
# --------------------------------------------------

initialize_session()


# --------------------------------------------------
# Header
# --------------------------------------------------

st.title("SharePoint RAG")

st.caption(
    "Ask questions about your indexed "
    "SharePoint documents and list items."
)


# --------------------------------------------------
# Sidebar
# --------------------------------------------------

with st.sidebar:

    st.header(
        "SharePoint RAG"
    )

    st.write(
        "Searches indexed SharePoint content "
        "using vector search, reranking, "
        "and an LLM."
    )

    st.divider()

    if st.button(
        "Clear conversation",
        use_container_width=True
    ):

        st.session_state.messages = []

        st.rerun()


# --------------------------------------------------
# Existing conversation
# --------------------------------------------------

for message in st.session_state.messages:

    with st.chat_message(
        message["role"]
    ):

        st.markdown(
            message["content"]
        )

        if (
            message["role"] == "assistant"
            and message.get("sources")
        ):

            display_sources(
                message["sources"]
            )


# --------------------------------------------------
# Chat input
# --------------------------------------------------

question = st.chat_input(
    "Ask a question about SharePoint..."
)


# --------------------------------------------------
# Process new question
# --------------------------------------------------

if question:

    # --------------------------------------------------
    # Store/display user question
    # --------------------------------------------------

    st.session_state.messages.append({
        "role": "user",
        "content": question
    })

    with st.chat_message(
        "user"
    ):

        st.markdown(
            question
        )

    # --------------------------------------------------
    # Run RAG pipeline
    # --------------------------------------------------

    with st.chat_message(
        "assistant"
    ):

        try:

            answer, sources = ask(
                question
            )

            st.markdown(
                answer
            )

            display_sources(
                sources
            )

            # --------------------------------------------------
            # Save answer in conversation
            # --------------------------------------------------

            st.session_state.messages.append({
                "role": "assistant",
                "content": answer,
                "sources": sources
            })

        except Exception as error:

            error_message = (
                "An error occurred while processing "
                "your question."
            )

            st.error(
                error_message
            )

            with st.expander(
                "Technical details"
            ):

                st.exception(
                    error
                )