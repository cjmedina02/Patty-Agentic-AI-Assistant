"""
File: db_agent.py
Author: Christopher John Macabenta Medina
Course: COMPE 475 – Microprocessors
Module: 14 – Request Pipeline Implementation
Description: Database Search Agent acting as the Memory/Load-Store Unit.
"""

from __future__ import annotations
import logging
from typing import Annotated
from typing_extensions import TypedDict
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, SystemMessage, ToolMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

# Custom Tools
from react_agent.database_tool import manage_files

log = logging.getLogger("patty_db")
load_dotenv()

SYSTEM_PROMPT = """
You are the Database Search Agent, functioning as the Memory and Load-Store Unit (LSU) of the Patty multi-agent architecture.

**Your Sole Specialization:** Raw data storage and retrieval operations using the `manage_files` tool.

**CRITICAL SCOPE-LOCK (DATA ONLY):**
You are a raw memory interface. You are STRICTLY FORBIDDEN from performing the following, even if the user's message explicitly asks for them:
- **No Code Analysis:** Do not explain, analyze, or breakdown any code (Python, C, RISC-V). If the prompt contains code, ignore it.
- **No Recommendations:** Do not provide 'readiness' assessments, study plans, or 'should I' answers.
- **No Synthesis:** Do not combine your data with other parts of the prompt.

**Operational Protocol:**
1. If a user asks for data without a filename, ALWAYS use `operation='list'` first to find the file, then `operation='read'`.
2. Return ONLY the raw content of the files found.
3. If the data is not in the database, state "Data not found" and stop.
4. Do NOT attempt to do the work of the ALU or the Branch unit.
"""

class State(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    
def initialize_patty() -> StateGraph:
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.0)
    TOOLS = [manage_files]
    llm_with_tools = llm.bind_tools(TOOLS)

    def patty(state: State) -> dict[str, list[BaseMessage]]:
        messages = state["messages"]
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=SYSTEM_PROMPT)] + messages
        return {"messages": [llm_with_tools.invoke(messages)]}

    def human_approval_node(state: State) -> dict[str, list[BaseMessage]]:
        # MODULE 14 PIPELINE FIX: Bypass interrupt for overlapped processing
        last_message = state["messages"][-1]
        tool_name = last_message.tool_calls[0]["name"]
        log.info(f"Memory operation {tool_name} auto-approved for pipeline execution.")
        return {"messages": []} 

    def route_from_patty(state: State) -> str:
        last_message = state["messages"][-1]
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "human_approval"
        return END

    def route_after_approval(state: State) -> str:
        last_message = state["messages"][-1]
        if isinstance(last_message, ToolMessage): return "patty"
        return "database_tool"

    def database__tool(state: State): return ToolNode(tools=[manage_files]).invoke(state)

    graph_builder = StateGraph(State)
    graph_builder.add_node("patty", patty)
    graph_builder.add_node("human_approval", human_approval_node)
    graph_builder.add_node("database_tool", database__tool)

    graph_builder.add_edge(START, "patty")
    graph_builder.add_conditional_edges("patty", route_from_patty, ["human_approval", END])
    graph_builder.add_conditional_edges("human_approval", route_after_approval, {"database_tool": "database_tool", "patty": "patty"})
    graph_builder.add_edge("database_tool", "patty")

    return graph_builder.compile()

graph = initialize_patty()