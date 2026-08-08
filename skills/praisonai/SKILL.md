---
name: praisonai
description: Build and run PraisonAI agents, multi-agent teams, workflows, MCP tools, RAG, and YAML/CLI apps with the praisonaiagents SDK. Use when working with PraisonAI, praisonaiagents, Agent/Agents/AgentFlow, MCP tools, memory, planning, or docs.praison.ai.
---

# PraisonAI

Production agent framework: single agents → multi-agent teams → workflows. Prefer existing Agent params over new APIs. Each feature works three ways: **Python, YAML, CLI**.

Docs: https://docs.praison.ai · Repo: https://github.com/MervinPraison/PraisonAI

## Install & env

```bash
pip install praisonaiagents          # core SDK
pip install praisonai                # CLI + wrapper
pip install "praisonai[claw]"        # dashboard + messaging channels
export OPENAI_API_KEY="..."          # or provider-specific keys
# Optional: TAVILY_API_KEY for web search / Claw
```

JS: `npm install praisonai`

## Decision guide

| Need | Use |
|------|-----|
| One-shot task | `Agent(...).start(prompt)` |
| Multi-agent sequence | `Agents(agents=[...]).start()` or `AgentFlow(steps=[...])` |
| Parallel / route / loop | `AgentFlow` + `parallel` / `route` / `loop` / `repeat` |
| Tools | `@tool` functions or `tools=MCP(...)` |
| Persist chat | `memory=True` and/or `db=db(...)` + `session_id` |
| Docs / files Q&A | `knowledge=["file.pdf", ...]` or RAG examples |
| No-code | `agents.yaml` + `praisonai agents.yaml` |
| Telegram/Slack/Discord | `praisonai claw` |

## Quick start (Python)

```python
from praisonaiagents import Agent

agent = Agent(instructions="You are a senior data analyst.")
agent.start("Analyze the top 3 tech trends and format as a markdown table.")
```

Multi-agent:

```python
from praisonaiagents import Agent, Agents

researcher = Agent(instructions="Research about AI")
writer = Agent(instructions="Summarise research findings")
Agents(agents=[researcher, writer]).start()
```

## Agent params (prefer these)

Common constructor knobs — `False` off, `True` defaults, Config object for custom:

| Param | Purpose |
|-------|---------|
| `instructions` | Primary system prompt (simplest) |
| `name` / `role` / `goal` / `backstory` | Identity (optional if `instructions` set) |
| `llm` / `model` | Model string or config (`gpt-4o`, `anthropic/claude-sonnet-4-5`) |
| `tools` | Callables, `@tool` funcs, or `MCP(...)` |
| `handoffs` | List of Agents for handoff (not deprecated `allow_delegation`) |
| `memory` | Short/long-term memory |
| `knowledge` | Files, URLs, or KnowledgeConfig |
| `planning` | Plan → execute |
| `reflection` | Self-review output |
| `guardrails` | Validate I/O |
| `web` | Web search/fetch (`web=True`) |
| `sandbox` | Isolated code execution |
| `hooks` | Lifecycle middleware |

Run methods: `.start(prompt)`, `.chat(message)` for conversational sessions.

**Do not** invent new Agent params when `instructions` / `tools` / `hooks` / `memory` already cover the need.

## Custom tools

```python
from praisonaiagents import Agent, tool

@tool
def search(query: str) -> str:
    """Search the web for information."""
    return f"Results for: {query}"

agent = Agent(instructions="Helpful assistant", tools=[search])
agent.start("Search for AI news")
```

Never use `eval`/`exec`/`subprocess` on model or user input inside tools.

## MCP tools

```python
from praisonaiagents import Agent, MCP

agent = Agent(tools=MCP("npx @modelcontextprotocol/server-memory"))
# HTTP: MCP("https://api.example.com/mcp")
# Explicit: MCP(command="npx", args=["-y", "@pkg"], env={"KEY": "..."})
```

## Workflows

```python
from praisonaiagents import Agent, AgentFlow
from praisonaiagents.workflows import parallel

a, b, synth = Agent(name="A", instructions="..."), Agent(name="B", instructions="..."), Agent(name="Synth", instructions="Combine findings")
result = AgentFlow(steps=[parallel([a, b]), synth]).start("Research topic X")
print(result["output"])
```

Patterns: sequential `steps=[...]`, `parallel([...])`, `route(...)`, `loop(...)`, `repeat(...)`.

## YAML (no code)

`agents.yaml`:

```yaml
framework: praisonai
topic: "Write a blog post about AI"
agents:
  researcher:
    role: Research Analyst
    goal: Research AI trends
    instructions: "Find accurate information"
  writer:
    role: Content Writer
    goal: Write engaging posts
    instructions: "Write clear content from research"
```

```bash
praisonai agents.yaml
```

Custom tools: put functions in `tools.py`; reference by function name under `tools:` in YAML.

## CLI cheat sheet

| Task | Command |
|------|---------|
| Run YAML / prompt | `praisonai`, `praisonai agents.yaml` |
| Chat / code | `praisonai --chat`, `praisonai code` |
| Research | `praisonai research`, `--deep-research` |
| Planning | `--planning` |
| Memory / knowledge | `praisonai memory …`, `praisonai knowledge …` |
| MCP | `praisonai mcp list` |
| Claw UI | `praisonai claw` → http://localhost:8082 |
| Flow builder | `praisonai flow` → http://localhost:7861 |

## Package map (contributing / monorepo)

| Package | Owns |
|---------|------|
| `praisonaiagents` | Core Agent, tools, memory, workflows, MCP |
| `praisonai-code` | Agentic CLI (`run`/`chat`/`code`) |
| `praisonai-bot` | Bots, gateway, channels |
| `praisonai` | Wrapper: serve, dashboard, adapters |

Tier-2 packages must not PyPI-depend on the wrapper; preserve old `praisonai.*` imports via shims. Full boundaries: repo `ARCHITECTURE.md` and `src/praisonai-agents/AGENTS.md`.

## Workflow checklist

```
- [ ] Choose Python vs YAML vs CLI
- [ ] Start with Agent(instructions=...) only; add tools/memory/planning as needed
- [ ] Prefer handoffs / Agents / AgentFlow over custom orchestration
- [ ] Set provider API key; add TAVILY_API_KEY if using web search
- [ ] Validate tools never execute untrusted code unsafely
- [ ] For monorepo changes: keep APIs minimal; no duplicate knobs
```

## More detail

- Patterns & advanced APIs: [reference.md](reference.md)
- Copy-paste recipes: [examples.md](examples.md)
