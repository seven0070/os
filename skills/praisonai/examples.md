# PraisonAI Examples

Minimal recipes. Expand from these; do not invent alternate APIs.

## 1. Single agent

```python
from praisonaiagents import Agent

agent = Agent(instructions="You are a Markdown Agent, output in markdown format")
agent.start("Write a blog post about AI")
```

## 2. Multi agents

```python
from praisonaiagents import Agent, Agents

research_agent = Agent(instructions="Research about AI")
summarise_agent = Agent(instructions="Summarise research agent's findings")
agents = Agents(agents=[research_agent, summarise_agent])
agents.start()
```

## 3. Sequential AgentFlow

```python
from praisonaiagents import Agent, AgentFlow

researcher = Agent(
    name="Researcher",
    role="Research Analyst",
    goal="Research and provide information about topics",
    instructions="Provide concise, factual information.",
)
writer = Agent(
    name="Writer",
    role="Content Writer",
    goal="Write engaging content based on research",
    instructions="Write clear content from the research provided.",
)

result = AgentFlow(
    name="Simple Agentic Pipeline",
    steps=[researcher, writer],
).start("What are the key benefits of AI agents?")
print(result["output"])
```

## 4. Parallel AgentFlow

```python
from praisonaiagents import Agent, AgentFlow
from praisonaiagents.workflows import parallel

market = Agent(name="Market", instructions="Analyze market trends briefly.")
competitor = Agent(name="Competitor", instructions="Analyze competitors briefly.")
synth = Agent(name="Synth", instructions="Combine findings into one summary.")

result = AgentFlow(
    steps=[parallel([market, competitor]), synth],
).start("Research the AI industry")
print(result["output"])
```

## 5. MCP (stdio)

```python
from praisonaiagents import Agent, MCP

agent = Agent(tools=MCP("npx @modelcontextprotocol/server-memory"))
agent.start("Remember that my favorite color is blue")
```

## 6. MCP with env

```python
from praisonaiagents import Agent, MCP

agent = Agent(
    tools=MCP(
        command="npx",
        args=["-y", "@modelcontextprotocol/server-brave-search"],
        env={"BRAVE_API_KEY": "your-key"},
    )
)
```

## 7. Safe calculator tool

```python
from praisonaiagents import Agent, tool
import ast
import operator

@tool
def calculate(expression: str) -> float:
    """Safely evaluate a numeric arithmetic expression."""
    _OPS = {
        ast.Add: operator.add, ast.Sub: operator.sub,
        ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.Pow: operator.pow, ast.USub: operator.neg, ast.UAdd: operator.pos,
    }

    def _safe_eval(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](_safe_eval(node.operand))
        raise ValueError("Unsupported expression")

    try:
        return _safe_eval(ast.parse(expression, mode="eval").body)
    except (ValueError, SyntaxError, TypeError, ZeroDivisionError, OverflowError) as e:
        raise ValueError("Invalid arithmetic expression") from e

agent = Agent(instructions="You are a helpful assistant", tools=[calculate])
agent.start("Calculate 15*4")
```

## 8. Memory + planning + web

```python
from praisonaiagents import Agent

agent = Agent(
    instructions="You are a research analyst who plans before acting.",
    memory=True,
    planning=True,
    web=True,
)
agent.start("Find recent developments in agent frameworks and summarize.")
```

## 9. YAML + tools.py

**agents.yaml**

```yaml
framework: praisonai
topic: "Calculate the sum of 25 and 15"
agents:
  calculator_agent:
    role: Calculator
    goal: Perform calculations
    instructions: "Use the add_numbers tool"
    tools:
      - add_numbers
```

**tools.py**

```python
def add_numbers(a: float, b: float) -> float:
    """Add two numbers together."""
    return a + b
```

```bash
praisonai agents.yaml
```

## 10. TypeScript

```bash
npm install praisonai
```

Follow `src/praisonai-ts/README.md` and `examples/js/` in the upstream repo for TS APIs (parity tracked in `PARITY.md`).
