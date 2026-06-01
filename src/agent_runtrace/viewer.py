from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any, Dict, List


def load_events(run_dir: str | Path) -> List[Dict[str, Any]]:
    trace_path = Path(run_dir) / "trace.jsonl"
    events = []
    if not trace_path.exists():
        raise FileNotFoundError(f"trace not found: {trace_path}")
    for line in trace_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            events.append(json.loads(line))
    by_id: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []
    for event in events:
        if event["id"] not in by_id:
            order.append(event["id"])
        by_id[event["id"]] = event
    return [by_id[i] for i in order]


def render_html(run_dir: str | Path) -> str:
    run_dir = Path(run_dir)
    metadata_path = run_dir / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
    events = load_events(run_dir)
    payload = json.dumps({"metadata": metadata, "events": events}, ensure_ascii=False)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>agent-runtrace</title>
<style>
:root {{ color-scheme: dark; --bg:#0b0f19; --panel:#121827; --muted:#8b9bb4; --text:#e8eefc; --line:#26334d; --accent:#7dd3fc; --bad:#fb7185; --ok:#86efac; }}
* {{ box-sizing: border-box; }}
body {{ margin:0; background:var(--bg); color:var(--text); font:14px/1.45 ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif; }}
header {{ padding:24px 28px; border-bottom:1px solid var(--line); background:#0f1624; }}
h1 {{ margin:0 0 8px; font-size:26px; letter-spacing:-.02em; }}
.sub {{ color:var(--muted); }}
main {{ display:grid; grid-template-columns: 380px 1fr; min-height:calc(100vh - 98px); }}
.timeline {{ border-right:1px solid var(--line); padding:18px; overflow:auto; }}
.event {{ width:100%; text-align:left; border:1px solid var(--line); background:var(--panel); color:var(--text); border-radius:12px; padding:12px; margin-bottom:10px; cursor:pointer; }}
.event:hover, .event.active {{ border-color:var(--accent); }}
.row {{ display:flex; align-items:center; justify-content:space-between; gap:8px; }}
.badge {{ font-size:12px; padding:2px 8px; border-radius:999px; background:#1d2a44; color:var(--accent); }}
.badge.error {{ color:var(--bad); }}
.badge.ok {{ color:var(--ok); }}
.name {{ font-weight:700; margin-top:8px; }}
.meta {{ color:var(--muted); font-size:12px; margin-top:4px; }}
.detail {{ padding:22px 28px; overflow:auto; }}
.card {{ border:1px solid var(--line); background:var(--panel); border-radius:14px; padding:18px; margin-bottom:16px; }}
h2 {{ margin:0 0 12px; font-size:20px; }}
h3 {{ margin:16px 0 8px; font-size:14px; color:var(--accent); text-transform:uppercase; letter-spacing:.08em; }}
pre {{ white-space:pre-wrap; word-break:break-word; background:#070b12; color:#dce7fa; border:1px solid var(--line); border-radius:10px; padding:14px; overflow:auto; max-height:460px; }}
.empty {{ color:var(--muted); padding:28px; }}
.stats {{ display:flex; gap:10px; flex-wrap:wrap; margin-top:14px; }}
.stat {{ background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:10px 12px; }}
</style>
</head>
<body>
<header>
  <h1>agent-runtrace</h1>
  <div class="sub">Local trace viewer for AI agent runs</div>
  <div id="stats" class="stats"></div>
</header>
<main>
  <section id="timeline" class="timeline"></section>
  <section id="detail" class="detail"><div class="empty">Select an event.</div></section>
</main>
<script id="payload" type="application/json">{html.escape(payload)}</script>
<script>
const data = JSON.parse(document.getElementById('payload').textContent);
const events = data.events;
const timeline = document.getElementById('timeline');
const detail = document.getElementById('detail');
const stats = document.getElementById('stats');
function esc(x) {{ return String(x ?? '').replace(/[&<>]/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;'}}[c])); }}
function pretty(x) {{ return esc(JSON.stringify(x ?? {{}}, null, 2)); }}
function renderStats() {{
  const types = events.reduce((m,e)=>(m[e.type]=(m[e.type]||0)+1,m),{{}});
  const failures = events.filter(e => e.error || (e.output && e.output.exit_code && e.output.exit_code !== 0)).length;
  stats.innerHTML = `<div class="stat"><b>${{events.length}}</b> events</div>` +
    Object.entries(types).map(([k,v])=>`<div class="stat"><b>${{v}}</b> ${{esc(k)}}</div>`).join('') +
    `<div class="stat"><b>${{failures}}</b> failures</div>`;
}}
function renderTimeline() {{
  timeline.innerHTML = events.map((e,i)=>`<button class="event" data-idx="${{i}}">
    <div class="row"><span class="badge ${{e.error ? 'error' : 'ok'}}">${{esc(e.type)}}</span><span class="meta">${{e.duration_ms ?? 0}}ms</span></div>
    <div class="name">${{esc(e.name)}}</div>
    <div class="meta">${{esc(e.started_at)}} ${{e.error ? ' · error' : ''}}</div>
  </button>`).join('');
  [...document.querySelectorAll('.event')].forEach(btn => btn.onclick = () => select(Number(btn.dataset.idx)));
  if (events.length) select(0);
}}
function select(i) {{
  document.querySelectorAll('.event').forEach(b => b.classList.remove('active'));
  document.querySelector(`.event[data-idx="${{i}}"]`)?.classList.add('active');
  const e = events[i];
  detail.innerHTML = `<div class="card">
    <div class="row"><h2>${{esc(e.name)}}</h2><span class="badge">${{esc(e.type)}}</span></div>
    <div class="meta">${{esc(e.started_at)}} → ${{esc(e.ended_at || 'running')}} · ${{e.duration_ms ?? 0}}ms</div>
    ${{e.error ? `<h3>Error</h3><pre>${{esc(e.error)}}</pre>` : ''}}
    <h3>Input</h3><pre>${{pretty(e.input)}}</pre>
    <h3>Output</h3><pre>${{pretty(e.output)}}</pre>
  </div>`;
}}
renderStats(); renderTimeline();
</script>
</body>
</html>"""


def write_viewer(run_dir: str | Path, out: str | Path | None = None) -> Path:
    run_dir = Path(run_dir)
    out_path = Path(out) if out else run_dir / "index.html"
    out_path.write_text(render_html(run_dir), encoding="utf-8")
    return out_path
