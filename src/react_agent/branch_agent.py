"""
File: branch_agent.py
Author: Christopher John Macabenta Medina
Course: COMPE 475 – Microprocessors
Module: 14 – Request Pipeline Implementation
Description: Decision/Routing Agent acting as the Branch/Control Unit.
"""

from __future__ import annotations
import logging
from typing import Annotated
from typing_extensions import TypedDict
from dotenv import load_dotenv

from langchain_tavily import TavilySearch
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, SystemMessage, ToolMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

log = logging.getLogger("korra_branch")
load_dotenv()

SYSTEM_PROMPT = """
You are the Decision/Routing Agent, functioning as the Branch/Control Unit of the Korra multi-agent architecture.

**Your Sole Specialization:** Conditional evaluation, trade-off analysis, and strategic recommendations.

**CRITICAL SCOPE-LOCK (STRATEGY ONLY):**
You are a high-level logic unit. You are STRICTLY FORBIDDEN from:
- **No Raw Data Fetching:** Do not attempt to use tools to search for files. You rely on the data provided by the Memory Unit.
- **No Raw Code Analysis:** Do not perform line-by-line code breakdowns. Use the report provided by the ALU.

**Operational Protocol:**
1. Look at the data retrieved by the DB agent.
2. Look at the technical report provided by the ALU agent.
3. Evaluate the criteria (e.g., "Is Grade A > Difficulty High?") and provide a final, definitive "Execution Path" or recommendation.
4. Always list the "Available Paths" and the "Final Recommendation" clearly.
"""

class State(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    
def initialize_korra() -> StateGraph:
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.5)
    tavily_tool = TavilySearch(max_results=2, include_answer=True)
    TOOLS = [tavily_tool]
    llm_with_tools = llm.bind_tools(TOOLS)

    def korra(state: State) -> dict[str, list[BaseMessage]]:
        messages = state["messages"]
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=SYSTEM_PROMPT)] + messages
        return {"messages": [llm_with_tools.invoke(messages)]}

    def human_approval_node(state: State) -> dict[str, list[BaseMessage]]:
        # MODULE 14 PIPELINE FIX: Bypass interrupt for overlapped processing
        last_message = state["messages"][-1]
        tool_name = last_message.tool_calls[0]["name"]
        log.info(f"Branch operation {tool_name} auto-approved for pipeline execution.")
        return {"messages": []} 

    def route_from_korra(state: State) -> str:
        last_message = state["messages"][-1]
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "human_approval"
        return END

    def route_after_approval(state: State) -> str:
        last_message = state["messages"][-1]
        if isinstance(last_message, ToolMessage): return "korra"
        tool_name = last_message.tool_calls[0]["name"]
        if tool_name == "tavily_search": return "tavily_tool"
        return END

    def tavily__tool(state: State): return ToolNode(tools=[tavily_tool]).invoke(state)

    graph_builder = StateGraph(State)
    graph_builder.add_node("korra", korra)
    graph_builder.add_node("human_approval", human_approval_node)
    graph_builder.add_node("tavily_tool", tavily__tool)

    graph_builder.add_edge(START, "korra")
    graph_builder.add_conditional_edges("korra", route_from_korra, ["human_approval", END])
    graph_builder.add_conditional_edges("human_approval", route_after_approval, {
        "tavily_tool": "tavily_tool",
        "korra": "korra"
    })
    graph_builder.add_edge("tavily_tool", "korra")

    return graph_builder.compile()

graph = initialize_korra()