# Korra AI Agent

**Author:** Christopher John Medina

---

## What is Korra?

Korra is an intelligent multi-agent AI assistant capable of understanding natural language requests and routing them to the right specialized agent to get the job done. Whether you need to look something up on the web, query a database, or analyze code, Korra figures out what you need and handles it — automatically.

Built using [LangGraph](https://github.com/langchain-ai/langgraph) and powered by OpenAI's large language models, Korra orchestrates a team of specialized agents that work together like a pipeline, each handling a distinct type of task.

---

## Features

- **Web Search** — Korra can search the internet in real time using Tavily to answer questions, find information, and retrieve up-to-date data.
- **Database Lookup** — Korra queries structured databases to retrieve and manage stored data on demand.
- **Code Analysis** — Korra reads, explains, and analyzes Python, C, C++, and RISC-V assembly code — identifying logic, bugs, and structure.
- **Intelligent Routing** — A supervisor agent acts as the brain, decoding each request and dispatching it to the most appropriate worker automatically.
- **Conflict Resolution** — Korra manages concurrent requests gracefully, ensuring agents don't step on each other and results are always delivered correctly.
- **File Statistics** — Korra can inspect and report statistics on files using a native C-backed tool.

---

## Built With

- [LangGraph](https://github.com/langchain-ai/langgraph) — multi-agent orchestration framework
- [LangChain](https://github.com/langchain-ai/langchain) — LLM tooling and integrations
- [langgraph-supervisor](https://github.com/langchain-ai/langgraph-supervisor) — supervisor agent pattern for multi-agent routing
- Python 3.11+

## APIs Used

- [OpenAI API](https://platform.openai.com/) — language model powering all agents (`gpt-4o` / `ChatOpenAI`)
- [Tavily Search API](https://tavily.com/) — real-time web search tool used by the ALU and Branch agents
- [LangSmith API](https://smith.langchain.com/) — tracing and observability for agent runs
- [GitHub API](https://docs.github.com/en/rest) *(optional)* — search and retrieve GitHub repositories

---

## Getting Started

### Prerequisites

- Python 3.11+
- [LangGraph CLI](https://github.com/langchain-ai/langgraph-studio)
- API keys for OpenAI, Tavily, and LangSmith

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
   LANGSMITH_PROJECT=new-agent
   LANGSMITH_API_KEY=your-langsmith-key
   OPENAI_API_KEY=your-openai-key
   TAVILY_API_KEY=your-tavily-key
   #GITHUB_TOKEN=your-github-token
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

## Project Structure

```
korra/
├── src/react_agent/
│   ├── graph.py              # Main supervisor graph and agent orchestration
│   ├── supervisor_agent.py   # Request routing and control logic
│   ├── db_agent.py           # Database search agent
│   ├── alu_agent.py          # Code analysis agent
│   ├── branch_agent.py       # Decision routing agent
│   ├── tools.py              # Web search and other tools
│   ├── prompts.py            # System prompt definitions
│   ├── state.py              # Shared agent state
│   ├── utils.py              # Utility functions
│   └── tools/
│       ├── file_stats_tool.py
│       └── file_stats.c
├── langgraph.json
├── pyproject.toml
├── Dockerfile
├── .env.example
└── README.md
```

