"""
File: graph.py
Author: Christopher John Macabenta Medina
Course: COMPE 475 - Microprocessors
Institution: San Diego State University
Module: 15 - Hazard Detection & Resolution (Section 4 - Final)
Version: 5.0

Description:
    Final integrated system + Campsite Checker extension.
    Layers all four hazard mechanisms on top of the Project 14 supervisor
    and adds a 4th functional unit: campsite_checker_agent.

      Section 1 - Structural Hazard: per-worker FIFO queue + serialization
      Section 2 - Data Hazard Forwarding: DB output bypassed to Decision
      Section 3 - Data Hazard Stalling: load-use bubble cycles
      Section 4 - Control Hazard: speculative queue tracker + flush on
                  'no record found', then reroute to error/help path
      Extension  - Campsite Checker Agent: Recreation.gov + ReserveCA
                   availability polling, Discord notifications, Azure state
    All detection logic lives in `_wire_hazard_detection`, which wraps
    each compiled worker graph's ainvoke.
"""

# ============================================================
# IMPORTS & PATH RESOLUTION
# ============================================================

import os
import sys
import asyncio
import logging
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langgraph_supervisor import create_supervisor, create_forward_message_tool

from react_agent.db_agent import graph as db_graph
from react_agent.alu_agent import graph as alu_graph
from react_agent.branch_agent import graph as branch_graph
from react_agent.campsite_agent import graph as campsite_graph

# Per rubric: starter hazard_logger helpers for all four mechanisms
from react_agent.hazard_logger import (
    structural_hazard,
    resume,
    forwarding,
    stall,
    bubble_cycle,
    control_hazard,
    flush,
)

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
# STRUCTURAL HAZARD STATE (Section 1)
# ============================================================

busy_workers = {
    "database_search_agent": None,
    "code_analysis_agent": None,
    "decision_routing_agent": None,
    "campsite_checker_agent": None,
}

worker_queues = {
    "database_search_agent": [],
    "code_analysis_agent": [],
    "decision_routing_agent": [],
    "campsite_checker_agent": [],
}

# ============================================================
# DATA HAZARD STATE (Sections 2 + 3)
# ============================================================

result_cache: dict[str, dict[str, str]] = {}

STALL_TICKS = 3
TICK_INTERVAL = 0.5

# ============================================================
# CONTROL HAZARD STATE (Section 4)
#   queued_workers -- request id -> list of speculatively-queued
#                     downstream workers. Mirrors how a CPU
#                     speculatively fetches past a branch.
# ============================================================

queued_workers: dict[str, list[str]] = {}


# ============================================================
# HELPERS
# ============================================================

def _extract_worker_text(result) -> str:
    if not isinstance(result, dict):
        return ""
    msgs = result.get("messages", [])
    for m in reversed(msgs):
        content = getattr(m, "content", None)
        msg_type = (getattr(m, "type", "") or m.__class__.__name__).lower()
        has_tool_calls = bool(getattr(m, "tool_calls", None))
        if content and "ai" in msg_type and not has_tool_calls:
            return content
    return ""


def _last_user_text(state_input) -> str:
    msgs = state_input.get("messages", []) if isinstance(state_input, dict) else []
    for m in reversed(msgs):
        msg_type = (getattr(m, "type", "") or m.__class__.__name__).lower()
        if "human" in msg_type:
            return (getattr(m, "content", "") or "").lower()
    return ""


def _producer_ready_in_cache(producer_name: str) -> bool:
    return any(producer_name in cache for cache in result_cache.values())


def _producer_dependency_for(worker_name: str, last_user_text: str) -> str | None:
    retrieval_verbs = (
        "look up", "retrieve", "query", "check the database",
        "find", "fetch", "get the",
    )
    if worker_name == "code_analysis_agent" and any(
        v in last_user_text for v in retrieval_verbs
    ):
        return "database_search_agent"
    return None


# ============================================================
# CONTROL HAZARD (Section 4)
# ============================================================

def _populate_queued_workers(rid: str, last_user_text: str) -> list[str]:
    """
    Speculatively queue downstream workers based on the user's prompt
    verbs -- the software analog of a CPU speculatively fetching past a
    branch before the branch result is known.
    """
    queue: list[str] = []
    if any(v in last_user_text for v in ("analyze", "explain", "break down", "examine code")):
        queue.append("code_analysis_agent")
    if any(v in last_user_text for v in (
        "recommend", "decide", "should i", "should they",
        "advise", "tell me if", "determine",
    )):
        queue.append("decision_routing_agent")
    queued_workers[rid] = queue
    return queue


def _is_no_record_output(text: str) -> bool:
    """
    Detect a no-record output by checking for not-found phrasing and the
    absence of positive data markers (grades, GPAs, course codes).
    A pure 'not found' response with no actual data trips the control
    hazard; a partial-data response with a stray 'not found' aside does not.
    """
    t = (text or "").lower()

    not_found_phrases = (
        "not found",
        "no record",
        "no such",
        "no data",
        "could not be retrieved",
        "couldn't be retrieved",
        "could not retrieve",
        "couldn't retrieve",
        "no information",
        "no entries",
        "do not have any record",
        "unable to find",
    )
    if not any(p in t for p in not_found_phrases):
        return False

    # Positive data markers: presence of any of these means DB returned
    # actual content, so this is NOT a control hazard.
    positive_markers = (
        "gpa:", "gpa is", "gpa of",
        "grade:", "grade is",
        "received a", "received an",
        "earned a", "earned an",
        "got a ", "got an ",
        "scored ",
        "compe", "math", "phys", "cs101", "cs201",
        " a-", " a+", " b+", " b-", " c+", " c-",
        "completed courses", "course history",
    )
    has_positive_data = any(m in t for m in positive_markers)

    return not has_positive_data


def _handle_control_hazard(rid: str, db_output_text: str) -> dict | None:
    """
    Emit [CONTROL HAZARD], [FLUSH] (with discarded worker names), and
    [RESUME] describing the rerouted path. Returns a replacement state
    dict that tells the supervisor to abandon downstream specialists
    and respond directly to the user.
    """
    queued = list(queued_workers.get(rid, []))

    control_hazard(
        f"database_search_agent returned 'no record found' (request {rid}); "
        f"speculatively-queued downstream workers invalidated"
    )
    flush(queued if queued else ["(none queued)"])
    resume(
        f"Rerouting request {rid} to error/help response path; "
        f"discarded {len(queued)} speculatively-queued worker(s)"
    )

    queued_workers[rid] = []  # clear after flush

    rerouted_text = (
        f"[CONTROL HAZARD - NO RECORD FOUND] {db_output_text}\n\n"
        f"The requested record does not exist in the database. The "
        f"speculatively-queued downstream specialists "
        f"({', '.join(queued) if queued else 'none'}) have been flushed "
        f"per the control-hazard policy. Respond DIRECTLY to the user "
        f"with a helpful 'record not found' message and DO NOT invoke "
        f"code_analysis_agent or decision_routing_agent."
    )

    return {"messages": [{"role": "ai", "content": rerouted_text}]}


# ============================================================
# DATA HAZARD STALL (Section 3)
# ============================================================

async def _stall_for_producer(worker_name: str, producer_name: str, rid: str) -> None:
    stall(f"{worker_name} waiting on {producer_name} output (request {rid})")
    tick = 0
    while True:
        tick += 1
        bubble_cycle(tick)
        await asyncio.sleep(TICK_INTERVAL)
        if tick >= STALL_TICKS and _producer_ready_in_cache(producer_name):
            break
        if tick >= STALL_TICKS * 2:
            break
    resume(
        f"{worker_name} input ready; producer {producer_name} "
        f"output now available (request {rid})"
    )


# ============================================================
# DATA HAZARD FORWARDING (Section 2)
# ============================================================

async def _maybe_forward(rid, worker_name, producer_result, original_input):
    if worker_name != "database_search_agent":
        return None

    last_user = _last_user_text(original_input)
    decision_verbs = (
        "recommend", "decide", "should i", "should they",
        "advise", "tell me if", "determine",
    )
    if not any(v in last_user for v in decision_verbs):
        return None

    db_text = _extract_worker_text(producer_result)
    result_cache.setdefault(rid, {})["database_search_agent"] = db_text

    forwarding(
        f"database_search_agent output -> decision_routing_agent "
        f"(request {rid}); supervisor bypassed"
    )

    msgs = original_input.get("messages", [])
    forwarded_input = {
        "messages": list(msgs) + [
            {
                "role": "user",
                "content": (
                    f"[Forwarded from database_search_agent] {db_text}\n\n"
                    f"Provide your recommendation based on this data."
                ),
            }
        ]
    }
    decision_result = await branch_graph.ainvoke(forwarded_input)
    decision_text = _extract_worker_text(decision_result)
    result_cache[rid]["decision_routing_agent"] = decision_text

    merged = (
        f"[FORWARDED: database_search_agent -> decision_routing_agent]\n"
        f"Both the database lookup AND the decision/routing recommendation have "
        f"already been completed via the forwarding bypass. The supervisor MUST "
        f"NOT invoke decision_routing_agent again for this request. Synthesize "
        f"the final answer for the user from the content below.\n\n"
        f"--- Database lookup ---\n{db_text}\n\n"
        f"--- Decision recommendation ---\n{decision_text}"
    )
    return {"messages": [{"role": "ai", "content": merged}]}

# ============================================================
# SUPERVISOR PRE-DISPATCH HOOK (all four hazard layers)
# ============================================================

def _wire_hazard_detection(worker_graph, worker_name):
    original_ainvoke = worker_graph.ainvoke
    original_invoke = worker_graph.invoke
    queue = worker_queues[worker_name]

    def _detect_and_serialize(rid):
        previous = busy_workers[worker_name]
        if previous is not None:
            queue.append(rid)
            structural_hazard(
                f"{worker_name} BUSY (previously serving {previous}); "
                f"queueing request {rid}; queue depth: {len(queue)}"
            )
            queue.pop(0)
            resume(
                f"{worker_name} FREE; request {rid} dequeued and starting"
            )
        busy_workers[worker_name] = rid

    async def hazard_aware_ainvoke(input_, config=None, **kwargs):
        rid = f"r{id(input_) & 0xFFFFFFFF:08x}"
        _detect_and_serialize(rid)

        last_user = _last_user_text(input_)

        # Section 4: speculatively queue downstream workers
        if worker_name == "database_search_agent":
            _populate_queued_workers(rid, last_user)

        # Section 3: load-use stall
        producer = _producer_dependency_for(worker_name, last_user)
        if producer is not None:
            await _stall_for_producer(worker_name, producer, rid)

        # Run the worker
        result = await original_ainvoke(input_, config, **kwargs)

        # Section 4: control-hazard validation after upstream completes
        if worker_name == "database_search_agent":
            db_text = _extract_worker_text(result)
            if _is_no_record_output(db_text):
                rerouted = _handle_control_hazard(rid, db_text)
                if rerouted is not None:
                    return rerouted

        # Cache + forwarding (Sections 2/3)
        result_cache.setdefault(rid, {})[worker_name] = _extract_worker_text(result)
        forwarded = await _maybe_forward(rid, worker_name, result, input_)
        return forwarded if forwarded is not None else result

    def hazard_aware_invoke(input_, config=None, **kwargs):
        rid = f"r{id(input_) & 0xFFFFFFFF:08x}"
        _detect_and_serialize(rid)
        return original_invoke(input_, config, **kwargs)

    worker_graph.ainvoke = hazard_aware_ainvoke
    worker_graph.invoke = hazard_aware_invoke


_wire_hazard_detection(db_graph, "database_search_agent")
_wire_hazard_detection(alu_graph, "code_analysis_agent")
_wire_hazard_detection(branch_graph, "decision_routing_agent")
_wire_hazard_detection(campsite_graph, "campsite_checker_agent")

# ============================================================
# WORKER REGISTRATION
# ============================================================

db_graph.name = "database_search_agent"
db_graph.description = "Use this worker ONLY when the request requires data retrieval or storage (e.g., student records, grades, course information)."

alu_graph.name = "code_analysis_agent"
alu_graph.description = "Use this worker ONLY when the request requires analyzing Python, C, or RISC-V assembly code (syntax, logic, bugs, explanation)."

branch_graph.name = "decision_routing_agent"
branch_graph.description = "Use this worker ONLY when the request requires decision-making, strategic routing, or recommendations based on criteria and trade-offs."

campsite_graph.name = "campsite_checker_agent"
campsite_graph.description = (
    "Use this worker ONLY when the request involves campsite availability, "
    "camping reservations, campgrounds, or outdoor trip planning. "
    "It checks Recreation.gov and Reserve California for tent site openings "
    "and can send Discord notifications when dates open up."
)

# ============================================================
# SUPERVISOR CONFIGURATION (Control Unit Microcode)
# ============================================================

SUPERVISOR_PROMPT = """
You are the Supervisor Agent, functioning as the Control Unit of the Patty multi-agent microprocessor architecture.

**Your Role (Instruction Decode & Dispatch):**
You read the user's request, decode the operations, and ensure every required functional unit is invoked.

**WORKER COVERAGE RULE (STRICT PIPELINING):**
A single request may contain multiple verb categories. Where applicable, invoke a separate specialist worker for EACH part of the prompt:
1. **'Look up / Retrieve / Query / Check student records'** -> `database_search_agent`.
2. **'Analyze / Explain / Break down code'** -> `code_analysis_agent`.
3. **'Recommend / Decide / Determine / Should I'** -> `decision_routing_agent`.
4. **'Campsite / Camping / Reservations / Check availability / Outdoor trip'** -> `campsite_checker_agent`.

**DATA HAZARD FORWARDING (HIGHEST PRIORITY -- CHECK THIS FIRST):**
If ANY message in the conversation starts with "[FORWARDED:", the runtime has already invoked the downstream specialist via the forwarding bypass. In that case:
- You MUST NOT invoke `decision_routing_agent` again for this request.
- The WORKER COVERAGE RULE below DOES NOT APPLY.
- Respond directly to the user by synthesizing the forwarded messages.
This rule overrides every other rule in this prompt.

**CONTROL HAZARD AWARENESS (Section 4):**
If a worker's output begins with "[CONTROL HAZARD - NO RECORD FOUND]" or otherwise indicates the upstream record was not found, the runtime has already flushed the speculatively-queued downstream specialists. You MUST NOT invoke `code_analysis_agent` or `decision_routing_agent` after such an output. Respond DIRECTLY to the user with a helpful "record not found" message.

**Multi-Agent Coordination & Synthesis:**
- **Single-Worker Requests:** If only ONE specialist is needed, delegate to it and use the `forward_message` tool. Stop immediately after.
- **Multi-Worker Requests:**
  1. Invoke the first required worker and wait for its output.
  2. Forward that output as context to the next required worker.
  3. ABSOLUTE RULE: When multiple workers are used, the `forward_message` tool is FORBIDDEN.
  4. Once all specialized workers have finished, synthesize the final answer yourself as direct text.

**Shared-Resource Conflict Resolution:**
- If multiple steps require the EXACT SAME worker, you MUST serialize them. Wait for the first fetch to complete before starting the second.
"""

# ============================================================
# GRAPH INITIALIZATION
# ============================================================

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.0)
forward_tool = create_forward_message_tool("supervisor")

graph = create_supervisor(
    [db_graph, alu_graph, branch_graph, campsite_graph],
    model=llm,
    prompt=SUPERVISOR_PROMPT,
    tools=[forward_tool]
)
