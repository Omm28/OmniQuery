from langgraph.graph import StateGraph, END

from app.state import GraphState
from app.nodes import decide_node, answer_node, search_node, synthesize_node
from app.logger import logger


def _route_decision(state: GraphState) -> str:
    decision = state.get("decision", "SEARCH")
    logger.debug("_route_decision | routing to %s", decision)
    return decision  

def build_graph() -> StateGraph:
    

    graph = StateGraph(GraphState)

    graph.add_node("decide_node",    decide_node)
    graph.add_node("answer_node",    answer_node)
    graph.add_node("search_node",    search_node)
    graph.add_node("synthesize_node", synthesize_node)

    graph.set_entry_point("decide_node")

    graph.add_conditional_edges(
        "decide_node",
        _route_decision,
        {
            "ANSWER": "answer_node",
            "SEARCH": "search_node",
        },
    )

    graph.add_edge("search_node", "synthesize_node")

    graph.add_edge("answer_node",    END)
    graph.add_edge("synthesize_node", END)

    compiled = graph.compile()
    logger.info("LangGraph compiled successfully")
    return compiled


agent_graph = build_graph()
