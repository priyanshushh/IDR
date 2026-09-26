from langgraph.graph import StateGraph,START,END
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.chat_graph.state import ChatState
from app.services.chat_graph.nodes import make_nodes
from langgraph.prebuilt import ToolNode, tools_condition


def build_chart_graph(db: AsyncSession):

    nodes = make_nodes(db)
    tool_node = ToolNode(nodes["tools"])

    graph = StateGraph(ChatState)

    graph.add_node(
        "load_history",
        nodes["load_history"]
    )

    graph.add_node(
        "resolve_permissions",
        nodes["resolve_permissions"]
    )

    graph.add_node(
        "embed_question",
        nodes["embed_question"]
    )

    graph.add_node(
        "retrieve_chunks",
        nodes["retrieve_chunks"]
    )

    graph.add_node(
        "generate_answer",
        nodes["generate_answer"]
    )

    graph.add_node(
        "tools",
        tool_node
    )

    graph.add_edge(START, "load_history")
    graph.add_edge("load_history", "resolve_permissions")
    graph.add_edge("resolve_permissions", "embed_question")
    graph.add_edge("embed_question", "retrieve_chunks")

    graph.add_edge(
        "retrieve_chunks",
        "generate_answer"
    )

    graph.add_conditional_edges(
        "generate_answer",
        tools_condition,
        {
            "tools": "tools",
            END: END,
        },
    )

    graph.add_edge("tools", "generate_answer")

    return graph.compile()