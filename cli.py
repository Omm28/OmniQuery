#!/usr/bin/env python
"""
cli.py
------
Command-line interface for the Web Search Agent.

Usage
-----
  python cli.py "What is the capital of France?"
  python cli.py "What is the latest OpenAI news?" --verbose

The CLI invokes the same LangGraph agent as the FastAPI server,
so results are identical to what you'd get via POST /ask.
"""

import sys
import argparse

# Ensure the project root is on the path when running directly
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.graph import agent_graph
from app.logger import logger


def run_query(query: str, verbose: bool = False) -> None:
    """Run the agent on a single query and print the result."""
    if verbose:
        print(f"\n🔍  Query  : {query}")
        print("⏳  Thinking...\n")

    try:
        final_state: dict = agent_graph.invoke({"query": query})
    except Exception as exc:
        print(f"❌  Error: {exc}", file=sys.stderr)
        sys.exit(1)

    answer   = final_state.get("answer", "No answer generated.")
    decision = final_state.get("decision", "SEARCH")
    source   = "llm" if decision == "ANSWER" else "web_search"

    if verbose:
        print(f"📡  Source  : {source}")
        print(f"🗂️  Decision: {decision}\n")
        print("─" * 60)

    print(f"\n💬  Answer:\n{answer}\n")

    if verbose:
        print("─" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Web Search Agent CLI — ask any question.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            '  python cli.py "What is Python?"\n'
            '  python cli.py "Latest AI news" --verbose\n'
        ),
    )
    parser.add_argument("query", help="The question to answer.")
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show decision and source details.",
    )
    args = parser.parse_args()
    run_query(args.query, verbose=args.verbose)


if __name__ == "__main__":
    main()
