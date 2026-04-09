from langgraph.graph import StateGraph, END
from langgraph.graph.message import MessagesState
from langgraph.prebuilt import ToolNode

from app.nodes import agent_node, should_continue
from app.tools.search import web_search
from app.logger import logger

def build_graph() -> StateGraph:
    graph = StateGraph(MessagesState)

    graph.add_node("agent", agent_node)
    graph.add_node("tools", ToolNode([web_search]))

    graph.set_entry_point("agent")

    graph.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            "__end__": END,
        },
    )

    
    graph.add_edge("tools", "agent")

    compiled = graph.compile()
    logger.info("LangGraph ReAct agent compiled successfully")
    return compiled

agent_graph = build_graph()
