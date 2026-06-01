# Field reports: running agent-runtrace across repositories

This document records real `agent-runtrace` runs against different repositories and project types. The goal is to keep the project honest: the tool should work outside its own demo.

## Summary

`agent-runtrace` was used against three repo contexts:

1. `agent-runtrace` itself: small Python package.
2. `NousResearch/hermes-agent`: larger real-world Python agent framework/tooling repo.
3. `sindresorhus/slash`: external JavaScript package cloned fresh from GitHub.

The important result: the tool was useful both for successful runs and for a setup failure. In the JS repo, the first `npm test` failed because dependencies were missing. The trace captured the exact failing command, stdout, stderr, and exit code. After `npm install`, the traced test run passed.

## Case 1: Python package smoke test

**Repository:** `pranjalbhatia710/agent-runtrace`

**Purpose:** prove the tool can trace its own test suite.

**Command:**

```bash
agent-runtrace run --name self-pytest -- uv run --with pytest --with hatchling python -m pytest tests -q
agent-runtrace inspect latest
```

**Observed result:**

```json
{
  "events": 1,
  "failures": 0,
  "types": ["tool"]
}
```

**Why this matters:**

This is the default package-maintainer use case: wrap the test command, keep a trace, and inspect the result when something fails.

## Case 2: Larger real-world Python agent repo

**Repository:** `NousResearch/hermes-agent`

**Purpose:** test the CLI against a larger agent/devtools codebase with an existing custom test runner.

**Command:**

```bash
PYTHONPATH=/home/pranjalbhatia/agent-runtrace/src \
  python -m agent_runtrace.cli run \
  --name hermes-agent-skills-tool-test \
  -- ./scripts/run_tests.sh tests/tools/test_skills_tool.py

PYTHONPATH=/home/pranjalbhatia/agent-runtrace/src \
  python -m agent_runtrace.cli inspect latest
```

**Observed result:**

```json
{
  "events": 1,
  "failures": 0,
  "types": ["tool"]
}
```

**Why this matters:**

This is closer to the target audience: people working on AI-agent infrastructure who already have non-trivial test commands. `agent-runtrace` does not need the repo to adopt a new framework. It can wrap the command the maintainer already uses.

## Case 3: Fresh external JavaScript package

**Repository:** `sindresorhus/slash`

**Purpose:** test the tool outside Python against a freshly cloned npm package.

### First run: failure before dependencies

**Command:**

```bash
git clone --depth 1 https://github.com/sindresorhus/slash.git /tmp/slash-agent-runtrace
cd /tmp/slash-agent-runtrace
PYTHONPATH=/home/pranjalbhatia/agent-runtrace/src \
  python -m agent_runtrace.cli run \
  --name external-js-npm-test \
  -- npm test
```

**Observed result:**

```json
{
  "events": 1,
  "failures": 1,
  "types": ["tool"]
}
```

The trace captured the reason:

```text
stdout:
> slash@5.1.0 test
> xo && ava && tsd

stderr:
sh: 1: xo: not found

exit_code: 127
```

**Why this matters:**

This is a good real-world debugging case. The test did not fail because the package code was broken. It failed because the repo was freshly cloned and dependencies were not installed. A trace makes that obvious.

### Second run: install dependencies

**Command:**

```bash
PYTHONPATH=/home/pranjalbhatia/agent-runtrace/src \
  python -m agent_runtrace.cli run \
  --name external-js-npm-install \
  -- npm install
```

**Observed result:**

```json
{
  "events": 1,
  "failures": 0,
  "types": ["tool"]
}
```

### Third run: test after install

**Command:**

```bash
PYTHONPATH=/home/pranjalbhatia/agent-runtrace/src \
  python -m agent_runtrace.cli run \
  --name external-js-npm-test-after-install \
  -- npm test
```

**Observed result:**

```json
{
  "events": 1,
  "failures": 0,
  "types": ["tool"]
}
```

**Why this matters:**

The same tool handled a Python package, a larger Python agent repo, and an npm package without repo-specific integration.

## What these runs revealed

The MVP already works as a command-level trace wrapper across repo types, but the field tests made the next product steps clearer.

### Useful now

- wrapping existing test commands
- preserving stdout/stderr/exit code
- distinguishing environment/setup failures from code failures
- creating local HTML viewers for command runs
- exporting trace bundles for issue reports

### Missing next

- multi-step sessions should be easier from the CLI, not only the SDK
- README should show real cross-repo examples
- trace summaries should include the command's last stderr lines
- optional `agent-runtrace doctor` could suggest fixes for common failures like missing npm deps
- CI docs should show upload-artifact workflows once GitHub workflow scope is available

## Product lesson

The strongest use case is not only "debug AI agent reasoning." The immediate broader wedge is:

> A local flight recorder for any agent-controlled repo operation.

That includes tests, installs, evals, browser scripts, codegen runs, and agent tool calls.
