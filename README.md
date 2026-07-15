# agent-runtrace

> Local-first trace recorder and HTML viewer for AI agent runs.

AI agents are hard to debug because the useful evidence is scattered across prompts, tool calls, shell output, file edits, retries, and final messages. `agent-runtrace` gives you a simple trace format and a standalone viewer so you can see what happened in one timeline.

Think **Playwright Trace Viewer for AI agents**, but local-first and tiny.

```bash
pip install agent-runtrace

agent-runtrace demo
agent-runtrace view latest --open
```

No SaaS. No database. No API key required for the demo.

## What it records

- LLM prompts and responses
- Tool calls
- Shell commands with stdout, stderr, exit code, and duration
- File artifacts
- Git diffs at the end of a run
- Errors and failed steps
- A shareable `.agenttrace.zip` bundle

## Quickstart from source

```bash
git clone https://github.com/pranjalbhatia710/agent-runtrace.git
cd agent-runtrace
python -m venv .venv
. .venv/bin/activate
pip install -e .
agent-runtrace demo
agent-runtrace view latest --open
```

## Python SDK

```python
from agent_runtrace import Recorder

rec = Recorder("fix failing test", redact_patterns=[r"sk-[A-Za-z0-9]+"])
rec.log_llm("plan", "The tests are failing. What should we do?", "Run the focused test, inspect the failure, patch the smallest path.", model="demo-model")
result = rec.run(["pytest", "-q"])
rec.log_llm("summary", "What happened?", f"pytest exited with {result.returncode}")
print(rec.finish())
```

## CLI

```bash
agent-runtrace run --name tests -- pytest -q
agent-runtrace demo
agent-runtrace view latest
agent-runtrace inspect latest
agent-runtrace export latest --out failing-run.agenttrace.zip
```

## Trace layout

```text
.agent-runs/
  latest -> 20260601T120000Z-demo/
  20260601T120000Z-demo/
    metadata.json
    trace.jsonl
    index.html
    files/
    diffs/
```

## Use cases

`agent-runtrace` is useful when an agent does more than return text:

- debug failed coding-agent runs
- attach reproducible traces to GitHub issues
- save CI artifacts for failed agent evals
- compare prompts or agent policies
- teach new contributors how an agent works
- audit risky commands and tool calls
- inspect browser-agent steps
- build regression tests for agent behavior
- demo agent products with evidence
- analyze latency and token/cost patterns

See [docs/use-cases.md](docs/use-cases.md) for concrete workflows and [docs/field-reports.md](docs/field-reports.md) for real runs across Python and JavaScript repositories.

## Why this should exist

Agent teams need repeatable debugging before they need another framework. Raw logs are not enough when an agent can call tools, edit files, retry, and fail halfway through. A trace should be something you can attach to an issue, inspect in CI, or use to reproduce a bad run.

## Roadmap

- [ ] OpenAI / Anthropic SDK helpers
- [ ] LangChain / LangGraph integration
- [ ] MCP proxy mode
- [ ] Pytest snapshot assertions for traces
- [ ] Secret redaction rules (SDK-supported with `Recorder(..., redact_patterns=[...])`; CLI presets still planned)
- [ ] Cost and token accounting
- [ ] Browser action capture
- [ ] GitHub Action that uploads trace artifacts on failure

## Contributing

This repo is intentionally small. Good first issues:

- Add a provider helper for one SDK
- Improve the static viewer UI
- Add redaction tests
- Add a sample trace from a real mini-agent
- Add CI artifact upload docs

## License

MIT
