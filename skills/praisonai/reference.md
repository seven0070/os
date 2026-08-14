# PraisonAI Reference

Read this when you need APIs beyond the SKILL.md quick start.

## Providers

Set the matching API key. Pass model via `llm=` / `model=`:

| Provider | Example model | Env |
|----------|---------------|-----|
| OpenAI | `gpt-4o`, `gpt-4o-mini` | `OPENAI_API_KEY` |
| Anthropic | `anthropic/claude-sonnet-4-5` | `ANTHROPIC_API_KEY` |
| Gemini | `gemini/gemini-2.0-flash` | `GOOGLE_API_KEY` / `GEMINI_API_KEY` |
| Groq | `groq/...` | `GROQ_API_KEY` |
| DeepSeek | `deepseek/...` | `DEEPSEEK_API_KEY` |
| Ollama | local model name + `base_url` | — |
| OpenRouter | `openrouter/...` | `OPENROUTER_API_KEY` |
| xAI | `xai/...` | `XAI_API_KEY` |

Examples live under `examples/python/providers/` and `examples/python/models/` in the repo.

## Config-object pattern

Feature flags accept `bool | str | Config`:

```python
from praisonaiagents import Agent
# from praisonaiagents import MemoryConfig, PlanningConfig, WebConfig  # when customizing

agent = Agent(
    instructions="Research assistant",
    memory=True,
    planning=True,
    web=True,
    reflection=True,
    guardrails=True,
)
```

Prefer bool defaults first. Use Config classes only when overriding defaults.

## Persistence

```python
from praisonaiagents import Agent, db

agent = Agent(
    name="Assistant",
    db=db(database_url="sqlite:///./praison.db"),  # or postgresql://...
    session_id="my-session",
    memory=True,
)
agent.chat("Hello!")
```

Supports PostgreSQL, MySQL, SQLite, MongoDB, Redis, and more — see docs `/docs/databases/overview`.

## Knowledge / RAG

```python
agent = Agent(
    instructions="Answer from the knowledge base",
    knowledge=["./docs/manual.pdf", "https://example.com/faq"],
)
agent.start("What is the refund policy?")
```

## Handoffs

```python
specialist = Agent(name="Specialist", instructions="Deep domain expert")
triage = Agent(
    name="Triage",
    instructions="Route hard questions to the specialist",
    handoffs=[specialist],
)
```

## Workflow helpers

Import from `praisonaiagents.workflows`:

| Helper | Behavior |
|--------|----------|
| `parallel([...])` | Run steps concurrently, then continue |
| `route(...)` | Conditional branching |
| `loop(...)` | Iterate over list/CSV items |
| `repeat(...)` | Evaluator-optimizer loops |

`AgentFlow(name=..., steps=[...]).start(input)` returns a dict with `"output"`.

## Deprecated — avoid

| Old | Use instead |
|-----|-------------|
| `allow_delegation=` | `handoffs=` |
| `allow_code_execution=` | `execution=ExecutionConfig(code_execution=True)` |
| `code_execution_mode=` | `execution=ExecutionConfig(code_mode="safe")` |
| `auto_save=` standalone | `memory=MemoryConfig(auto_save="name")` |

## Monorepo install order (dev)

`praisonai-agents` → `praisonai-code` → `praisonai-bot` → `praisonai-train` → `praisonai-browser` → `praisonai-mcp` → `praisonai-sandbox` → `praisonai-deploy` → `praisonai`

Do not recreate `src/praisonai/praisonai_code/` — it shadows the real package.

## Design rules (SDK changes)

1. Stay lightweight — reject scope creep.
2. Prefer existing Agent surfaces (`instructions`, `backstory`, `tools`, `hooks`, `memory`).
3. No new knobs without a live consumer.
4. Preserve backward-compat shims for moved imports.
5. Features should work via CLI, YAML, and Python when applicable.

## Official links

- Docs: https://docs.praison.ai
- MCP transports: https://docs.praison.ai/docs/mcp/transports
- Tools: https://docs.praison.ai/docs/tools/tools
- AgentFlow: https://docs.praison.ai/docs/concepts/agentflow
- CLI reference: https://docs.praison.ai/docs/cli/cli-reference
- Deep research: https://docs.praison.ai/docs/agents/deep-research
