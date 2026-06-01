# Use cases

`agent-runtrace` is for people building, testing, or operating AI agents that do more than return text. If an agent calls tools, edits files, runs commands, controls a browser, or retries after failure, a plain log is usually not enough. A trace gives you a timeline you can inspect, share, and compare.

## 1. Debug a failed coding-agent run

**User:** developer using Claude Code, Codex, Aider, OpenHands, Cursor agents, or a custom coding agent.

**Problem:** the agent says it fixed the bug, but tests still fail or the diff is strange.

**How agent-runtrace helps:**

- records every shell command the agent ran
- captures stdout, stderr, exit code, and duration
- stores final git diff
- shows the run as a timeline instead of a wall of logs

**Example flow:**

```bash
agent-runtrace run --name fix-tests -- pytest -q
agent-runtrace view latest --open
```

**What the trace answers:**

- Did the agent run the right test?
- Did it ignore a failing command?
- Did it change files after the final test run?
- Where did the first failure happen?

## 2. Attach a reproducible trace to GitHub issues

**User:** OSS maintainer or contributor.

**Problem:** bug reports about agent behavior are vague: “the agent failed” or “the tool crashed.”

**How agent-runtrace helps:**

- exports a `.agenttrace.zip` bundle
- includes metadata, events, command output, and artifacts
- lets maintainers inspect what happened without asking for screenshots

**Example flow:**

```bash
agent-runtrace demo
agent-runtrace export latest --out failure.agenttrace.zip
```

**Good issue attachment:**

```text
I attached failure.agenttrace.zip. It includes the tool call timeline, stdout/stderr, and final git diff.
```

## 3. CI artifact for failed agent-eval runs

**User:** team running agent evaluations in CI.

**Problem:** a benchmark failed in CI, but the logs are too long to understand.

**How agent-runtrace helps:**

- wraps an eval command
- writes a local trace artifact
- exports it when the job fails
- makes CI failures inspectable after the fact

**Example flow:**

```bash
agent-runtrace run --name eval-suite -- python evals/run.py
agent-runtrace export latest --out eval-failure.agenttrace.zip
```

**What the trace answers:**

- Which task failed?
- Which command or tool call failed?
- Did the agent time out, return bad output, or call the wrong tool?
- How much useful work happened before failure?

## 4. Compare two prompts or agent policies

**User:** AI engineer tuning prompts, tool policies, or system instructions.

**Problem:** a prompt change “feels better,” but nobody knows what behavior changed.

**How agent-runtrace helps:**

- run the same task twice
- compare traces side by side manually today
- later, use trace diffing as a first-class feature

**Example flow:**

```bash
agent-runtrace run --name old-prompt -- python run_agent.py --prompt old.md
agent-runtrace run --name new-prompt -- python run_agent.py --prompt new.md
agent-runtrace view .agent-runs/<old-run>
agent-runtrace view .agent-runs/<new-run>
```

**What to compare:**

- number of tool calls
- failed commands
- time to success
- files touched
- final output quality
- unnecessary retries

## 5. Teach new contributors how an agent actually works

**User:** student, OSS maintainer, or team lead onboarding developers.

**Problem:** agent architectures are hard to understand from code alone.

**How agent-runtrace helps:**

- creates a readable execution timeline
- shows prompts, tool calls, and outputs in order
- makes agent behavior concrete for people who are new to the codebase

**Example use:**

- run a small demo agent
- open the trace in a workshop or README
- walk through the timeline step by step

**What people learn:**

- how the agent decides what to do next
- what evidence each step used
- how failures propagate
- where guardrails should be added

## 6. Build safer agent permission systems

**User:** developer building a sandbox, MCP proxy, or approval layer.

**Problem:** before enforcing policies, you need to know what the agent is actually doing.

**How agent-runtrace helps:**

- records commands and tool calls
- creates an audit trail
- surfaces risky behavior for later policy work

**Future policy examples:**

```yaml
blocked_commands:
  - rm -rf
  - curl | sh
allowed_paths:
  - ./src
  - ./tests
approval_required:
  - git push
  - deploy
```

**What the trace answers:**

- Which operations should require approval?
- Which commands happen frequently and should be allowlisted?
- Which paths does the agent actually need?

## 7. Debug browser or web agents

**User:** builder using Playwright, Stagehand, Browser Use, Skyvern, or custom browser automation.

**Problem:** browser agents fail because of state, selectors, timeouts, auth, or page changes.

**How agent-runtrace can help now:**

- record high-level actions as custom events
- attach screenshots or HTML snapshots with `capture_file`
- inspect the timeline of browser steps

**Example SDK pattern:**

```python
from agent_runtrace import Recorder

rec = Recorder("browser checkout task")
rec.log("browser", "open page", output={"url": "https://example.com"})
rec.log("browser", "click", input={"selector": "text=Checkout"})
rec.capture_file("screenshot-after-click.png")
rec.finish()
```

**Future integration:** direct Playwright step capture.

## 8. Create regression tests for agents

**User:** team maintaining an agent over time.

**Problem:** agent behavior regresses silently after model, prompt, or tool changes.

**How agent-runtrace helps:**

- creates structured traces that can become snapshots
- enables future assertions over runs
- makes failures easier to inspect when a regression appears

**Possible assertions:**

- no more than N tool calls
- command must exit 0
- no blocked command appears
- final diff only touches allowed files
- no secret-like string appears in output

## 9. Demo an agent product with evidence

**User:** founder, student builder, or OSS maintainer launching an agent tool.

**Problem:** agent demos often look hand-wavy. People want to see what happened under the hood.

**How agent-runtrace helps:**

- generate a trace from the demo
- publish a screenshot/GIF of the viewer
- include the trace artifact in the repo

**Marketing angle:**

```text
Here is the agent run, not just the final answer.
You can inspect every tool call and failure in the trace.
```

This builds trust.

## 10. Audit agent cost and latency

**User:** developer or team trying to make agents cheaper and faster.

**Problem:** agent runs get expensive through repeated calls, retries, and unnecessary commands.

**How agent-runtrace helps now:**

- records durations per event
- can store token counts in `log_llm`
- shows repeated or slow steps

**Future features:**

- cost summaries
- token charts
- slowest step detection
- per-model cost comparison

## Best initial target users

The first audience should be narrow:

1. people building coding agents
2. people evaluating coding/browser agents
3. OSS maintainers debugging agent bug reports
4. AI devtool builders who want local-first traces

Avoid pitching it as generic observability at first. The sharper pitch is:

> A local trace viewer for debugging AI agents that use tools.

## What to build next from these use cases

Highest-impact next features:

1. **Secret redaction** before trace writing.
2. **OpenAI/Anthropic helpers** for recording real LLM calls.
3. **GitHub Actions artifact docs** for failed CI runs.
4. **Trace diff** for prompt/policy comparison.
5. **Playwright/browser event helpers** for web-agent debugging.
