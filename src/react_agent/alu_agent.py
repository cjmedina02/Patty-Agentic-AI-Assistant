"""
File: alu_agent.py
Author: Christopher John Macabenta Medina
Course: COMPE 475 – Microprocessors
Module: 14 – Request Pipeline Implementation
Description: Code Analysis Agent acting as the Arithmetic Logic Unit (ALU).
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

# Custom Tools
from react_agent.tools.file_stats_tool import analyze_file_statistics

log = logging.getLogger("korra_alu")
load_dotenv()

SYSTEM_PROMPT = """
You are the Code Analysis Agent, functioning as the Arithmetic Logic Unit (ALU) of the Korra multi-agent architecture.

**Your Sole Specialization:** Technical, computational analysis of Python, C, and RISC-V assembly code.

**CRITICAL SCOPE-LOCK (ANALYSIS ONLY):**
You are a processing unit, not a decision-making unit. You are STRICTLY FORBIDDEN from:
- **No Data Retrieval:** Do not attempt to guess or "look up" student records or grades.
- **No Recommendations:** Do not produce 'suggestions,' 'study plans,' or 'career advice.' 
- **No Strategic Decisions:** Do not decide if a student is 'ready' or if a project is 'too hard.'

**Operational Protocol:**
- Identify instructions, register usage (RISC-V), memory management (C), and logic flow (Python).
- Provide factual, technical breakdowns only. 
- If the user asks for a recommendation, provide the analysis and state: "Analysis complete. Decision/Routing unit must provide recommendations."
"""

class State(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    
def initialize_korra() -> StateGraph:
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.2)
    tavily_tool = TavilySearch(max_results=2, include_answer=True)
    file_stats_tool = analyze_file_statistics

    TOOLS = [tavily_tool, file_stats_tool]
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
        log.info(f"ALU operation {tool_name} auto-approved for pipeline execution.")
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
        if tool_name == file_stats_tool.name: return "file_stats_tool"
        return END

    def tavily__tool(state: State): return ToolNode(tools=[tavily_tool]).invoke(state)
    def file_stats__tool(state: State): return ToolNode(tools=[file_stats_tool]).invoke(state)

    graph_builder = StateGraph(State)
    graph_builder.add_node("korra", korra)
    graph_builder.add_node("human_approval", human_approval_node)
    graph_builder.add_node("tavily_tool", tavily__tool)
    graph_builder.add_node("file_stats_tool", file_stats__tool)

    graph_builder.add_edge(START, "korra")
    graph_builder.add_conditional_edges("korra", route_from_korra, ["human_approval", END])
    graph_builder.add_conditional_edges("human_approval", route_after_approval, {
        "tavily_tool": "tavily_tool",
        "file_stats_tool": "file_stats_tool",
        "korra": "korra"
    })
    graph_builder.add_edge("tavily_tool", "korra")
    graph_builder.add_edge("file_stats_tool", "korra")

    return graph_builder.compile()

graph = initialize_korra()