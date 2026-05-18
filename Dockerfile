FROM python:3.11-slim

WORKDIR /app

# Install system build tools (gcc, make, etc.)
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy project source code (including pyproject.toml and src/)
COPY . .

# Compile the C tool
RUN gcc -Wall -Wextra -std=c11 -O2 -o src/react_agent/tools/file_stats src/react_agent/tools/file_stats.c

# Install Python dependencies
# First install your local project in editable mode
RUN pip install --upgrade pip && \
    pip install -e . && \
    pip install langgraph-cli langchain-openai langchain-tavily langchain-mcp-adapters "langgraph-cli[inmem]"

# Open the dev server port
EXPOSE 2024

# Start LangGraph dev server
CMD ["langgraph", "dev", "--host", "0.0.0.0"]