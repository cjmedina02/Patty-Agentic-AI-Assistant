# Korra — CPU Hazard Detection & Resolution Agent System

**Course:** COMPE 475 – Microprocessors  
**Institution:** San Diego State University  
**Author:** Christopher John Medina

---

## Overview

Korra is a multi-agent AI system built with [LangGraph](https://github.com/langchain-ai/langgraph) that simulates how a modern CPU pipeline detects and resolves hazards. Each agent in the system maps to a functional unit in a real processor pipeline, and the supervisor acts as the CPU Control Unit — routing tasks, detecting conflicts, and applying resolution strategies in real time.

The system is built on top of the LangGraph ReAct agent template and extended across four sections (Modules 13–15) to layer increasingly complex hazard mechanisms.

---

## Architecture

```
                        ┌─────────────────────────┐
                        │   Supervisor Agent       │
                        │   (CPU Control Unit)     │
                        └────────────┬────────────┘
               ┌────────────────────┼────────────────────┐
               ▼                    ▼                    ▼
   ┌───────────────────┐  ┌──────────────────┐  ┌──────────────────────┐
   │  DB Agent         │  │  ALU Agent       │  │  Branch Agent        │
   │  (Memory Unit)    │  │  (Arithmetic)    │  │  (Decision Routing)  │
   └───────────────────┘  └──────────────────┘  └──────────────────────┘
```

The supervisor evaluates every incoming request, decodes its intent, and dispatches it to the correct worker agent — exactly like a CPU Control Unit decoding instructions and routing them to functional units.

---

## Hazard Mechanisms (Sections 1–4)

### Section 1 — Structural Hazard
- **Problem:** Two requests try to use the same worker (functional unit) simultaneously.
- **Solution:** Per-worker FIFO queues + serialization. The supervisor holds back the second request until the first completes.
- **Key file:** `graph.py` (`busy_workers`, `worker_queues`)

### Section 2 — Data Hazard: Forwarding
- **Problem:** A downstream agent needs a result before it has been written back.
- **Solution:** The DB agent's output is forwarded directly to the Decision/Branch agent, bypassing the write-back stage.
- **Key file:** `graph.py` (forwarding logic in `_wire_hazard_detection`)

### Section 3 — Data Hazard: Stalling
- **Problem:** A load-use dependency — the result isn't ready in time even with forwarding.
- **Solution:** Bubble cycles are inserted to stall the pipeline until the value is available.
- **Key file:** `graph.py` (`stall`, `bubble_cycle` from `hazard_logger`)

### Section 4 — Control Hazard (Final)
- **Problem:** Speculative execution — the pipeline fetches instructions down a predicted branch that turns out to be wrong.
- **Solution:** A speculative queue tracker monitors in-flight dispatches. On a "no record found" result, the pipeline is flushed and rerouted to an error/help path.
- **Key file:** `graph.py` (`control_hazard`, `flush` from `hazard_logger`)

---

## Project Structure

```
korra/
├── src/react_agent/
│   ├── graph.py              # Main supervisor graph + all 4 hazard mechanisms
│   ├── supervisor_agent.py   # CPU Control Unit (routing logic)
│   ├── db_agent.py           # Database Search Agent (Memory Unit)
│   ├── alu_agent.py          # Code Analysis Agent (ALU)
│   ├── branch_agent.py       # Decision Routing Agent (Branch Unit)
│   ├── hazard_logger.py      # Logging helpers for all hazard types
│   ├── prompts.py            # System prompt definitions
│   ├── state.py              # Shared graph state
│   ├── context.py            # Runtime context configuration
│   ├── tools.py              # LangChain tools (Tavily search, etc.)
│   ├── utils.py              # Utility functions
│   └── tools/
│       ├── file_stats_tool.py  # File statistics tool
│       └── file_stats.c        # Native C helper for file stats
├── langgraph.json            # LangGraph graph entry point config
├── pyproject.toml            # Project dependencies
├── Dockerfile                # Container deployment config
├── Makefile                  # Dev shortcuts
├── .env.example              # Required environment variables
└── README.md
```

---

## Getting Started

### Prerequisites

- Python 3.11+
- [LangGraph CLI](https://github.com/langchain-ai/langgraph-studio)
- API keys for Anthropic and/or OpenAI (and optionally Tavily)

### Setup

1. **Clone the repo:**
   ```bash
   git clone https://github.com/<your-username>/<your-repo-name>.git
   cd <your-repo-name>
   ```

2. **Create your `.env` file:**
   ```bash
   cp .env.example .env
   ```

3. **Add your API keys to `.env`:**
   ```
   ANTHROPIC_API_KEY=your-anthropic-key
   OPENAI_API_KEY=your-openai-key
   TAVILY_API_KEY=your-tavily-key
   ```

4. **Install dependencies:**
   ```bash
   pip install -e .
   ```

5. **Run with LangGraph CLI:**
   ```bash
   langgraph dev
   ```

---

## Dependencies

| Package | Purpose |
|---|---|
| `langgraph` | Multi-agent graph framework |
| `langchain-anthropic` | Claude model integration |
| `langchain-openai` | GPT model integration |
| `langchain-tavily` | Web search tool |
| `python-dotenv` | Environment variable management |

---

## Model Configuration

The system defaults to `claude-sonnet-4-5-20250929`. To switch models, update the model string in `src/react_agent/context.py` or pass it at runtime in LangGraph Studio.

---

## Course Context

This project was built incrementally across COMPE 475 modules:

| Module | Topic |
|---|---|
| 13 | Pipeline foundation & supervisor routing |
| 14 | Request pipeline implementation & worker agents |
| 15 | Hazard detection (structural, data, control) |

Each hazard section adds a new detection and resolution layer on top of the previous one, mirroring how real CPU microarchitecture handles pipeline conflicts.

---

## License

MIT
