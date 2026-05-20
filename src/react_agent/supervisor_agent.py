"""
File: supervisor_agent.py
Author: Christopher John Macabenta Medina
Course: COMPE 475 – Microprocessors
Institution: San Diego State University
Module: 14 – Request Pipeline Implementation (Section 1)
Version: 1.0

Description:
    Supervisor Agent acting as the CPU Control Unit.
    Evaluates incoming requests, decodes the required operations,
    and dispatches tasks to the appropriate specialized functional units.
    (Workers are stubbed for Section 1 routing verification).
"""

# ============================================================
# IMPORTS
# ============================================================

import os
import logging
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langgraph_supervisor import create_supervisor

# ============================================================
# LOGGING SETUP
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("patty_supervisor")

load_dotenv()

# ============================================================
# SECTION 1 WORKER STUBS (Functional Unit Interfaces)
# ============================================================

@tool
def database_search_agent(messages: list) -> str:
    """
    Use this worker ONLY when the request requires data retrieval 
    (e.g., student records, grades, course information, conversation history).
    """
    return "[ROUTED TO: Database Search Agent / Memory Unit]"

@tool
def code_analysis_agent(messages: list) -> str:
    """
    Use this worker ONLY when the request requires analyzing 
    Python, C, or RISC-V assembly code (syntax, logic, bugs, explanation).
    """
    return "[ROUTED TO: Code Analysis Agent / ALU]"

@tool
def decision_routing_agent(messages: list) -> str:
    """
    Use this worker ONLY when the request requires decision-making, 
    strategic routing, or recommendations based on criteria and trade-offs.
    """
    return "[ROUTED TO: Decision/Routing Agent / Branch Unit]"
# ============================================================
# SUPERVISOR CONFIGURATION (Control Unit Microcode)
# ============================================================

SUPERVISOR_PROMPT = """
You are the Supervisor Agent, functioning as the Control Unit of the Patty multi-agent microprocessor architecture.

**Your Role (Instruction Decode & Dispatch):**
You do not execute tasks yourself. You read the user's request, decode what needs to be done, and dispatch the work to the correct specialized worker agents.

**Routing Rules:**
1. **Database Search Agent:** Delegate here for memory/storage access (grades, records, past info).
2. **Code Analysis Agent:** Delegate here for ALU operations (reviewing Python, C, RISC-V code).
3. **Decision/Routing Agent:** Delegate here for control flow (weighing options, making career/study recommendations).

**Multi-Agent Coordination & Synthesis:**
- If a request requires multiple steps (e.g., "Get my grades and tell me if I should take this class"), you must orchestrate a pipeline.
- Call the first necessary worker, wait for its observation, then pass that data to the next necessary worker.
- Once all necessary workers have completed their tasks, synthesize their outputs into a final, coherent response for the user.
"""

# ============================================================
# GRAPH INITIALIZATION
# ============================================================

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.0)

# Create the supervisor graph using the stubs
graph = create_supervisor(
    [database_search_agent, code_analysis_agent, decision_routing_agent],
    model=llm,
    prompt=SUPERVISOR_PROMPT
)