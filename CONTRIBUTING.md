# Contributing

Thanks for helping improve agent-runtrace.

## Local setup

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e .
python -m unittest discover -s tests
agent-runtrace demo
agent-runtrace inspect latest
```

## Good first issues

- Add redaction helpers for obvious secret patterns.
- Add SDK examples for OpenAI or Anthropic.
- Improve the viewer styling or filtering.
- Add GitHub Actions docs for uploading trace artifacts.

## Design principles

- Local-first.
- Plain files over services.
- Useful without API keys.
- Small surface area.
- Debuggability over framework lock-in.
