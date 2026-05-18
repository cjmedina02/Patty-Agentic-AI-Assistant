# Korra — CPU Hazard Detection & Resolution Agent System

**Course:** COMPE 475 – Microprocessors  
**Institution:** San Diego State University  
**Author:** Christopher John Macabenta Medina

---

## Overview

Korra is a multi-agent AI system built with [LangGraph](https://github.com/langchain-ai/langgraph) that simulates how a modern CPU pipeline detects and resolves hazards. Each agent maps to a functional unit in a real processor pipeline, and the supervisor acts as the CPU Control Unit — decoding requests, routing them to the right worker, and applying resolution strategies when pipeline conflicts arise.

The system implements all four classical CPU hazard types — structural, data forwarding, data stalling, and control — entirely in software using conversational AI agents.

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

The supervisor evaluates every incoming request, decodes its intent, and dispatches it to the correct worker agent — mirroring how a real CPU Control Unit routes instructions to functional units.

---

## What It Does

### Structural Hazard Detection & Resolution
When two requests compete for the same worker simultaneously, Korra detects the conflict and serializes execution using per-worker FIFO queues — preventing resource contention the same way a CPU stalls a conflicting instruction until the shared unit is free.

### Data Hazard — Forwarding
When a downstream agent depends on a result that hasn't been written back yet, Korra bypasses the write-back stage and forwards the output directly — eliminating the stall that would otherwise occur.

### Data Hazard — Stalling (Bubble Cycles)
For load-use dependencies that forwarding can't resolve, Korra inserts bubble cycles into the pipeline, holding back dependent operations until the required value is ready — matching real processor behavior under true data dependencies.

### Control Hazard — Speculative Execution & Flush
Korra speculatively dispatches instructions down the predicted execution path. If the prediction is wrong (e.g., "no record found"), it detects the misprediction, flushes the speculative queue, and reroutes to the correct error or help path — just like a branch misprediction flush in a real CPU pipeline.

---

## Project Structure

```
korra/
├── src/react_agent/
│   ├── graph.py              # Main supervisor graph + all hazard mechanisms
│   ├── supervisor_agent.py   # CPU Control Unit (routing logic)
│   ├── db_agent.py           # Database Search Agent (Memory Unit)
│   ├── alu_agent.py          # Code Analysis Agent (ALU)
│   ├── branch_agent.py       # Decision Routing Agent (Branch Unit)
│   ├── hazard_logger.py      # Hazard event logging for all four types
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

## License

MIT
