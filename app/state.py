from typing import TypedDict

class GraphState(TypedDict, total=False):

    query: str
    decision: str
    search_results: str
    answer: str
