# bench_all.py
import json, subprocess, sys, os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PY = sys.executable  # même venv que ton terminal

def tool_path(rel):
    p1 = ROOT / "src" / rel
    if p1.exists(): return str(p1)
    p2 = ROOT / "src" / "test" / rel
    if p2.exists(): return str(p2)
    return str(p1)

def resolve_target(name: str) -> str:
    p = Path(name)
    if p.is_absolute() and p.exists(): return str(p)
    for cand in [ROOT / name, ROOT / "src" / name, ROOT / "src" / "test" / name, ROOT / "python" / name]:
        if cand.exists(): return str(cand.resolve())
    return str((ROOT / name).resolve())

def extract_json(text: str) -> dict | None:
    """Tente d'extraire le dernier objet JSON dans un texte pollué par des logs."""
    s = text.strip()
    if not s: return None
    end = s.rfind('}')
    if end == -1: return None
    # essaie depuis chaque '{' vers l'arrière jusqu'au '}' final
    starts = [i for i, ch in enumerate(s[:end+1]) if ch == '{']
    for start in reversed(starts):
        try:
            return json.loads(s[start:end+1])
        except Exception:
            pass
    return None

TOOLS = [
    ("codecarbon",    [PY, tool_path("codecarbon-api.py")]),
    ("carbontracker", [PY, tool_path("carbontracker-api.py")]),
    ("eco2ai",        [PY, tool_path("eco2ai-api.py")]),
    ("tracarbon",     [PY, tool_path("tracarbon-api.py")]),
]

target = resolve_target(sys.argv[1] if len(sys.argv) > 1 else "bench_cpu_60s.py")

def run(cmd):
    env = os.environ.copy()
    env.setdefault("CODECARBON_LOG_LEVEL", "error")  # réduit le bruit
    p = subprocess.run(cmd + [target], capture_output=True, text=True, cwd=str(ROOT), env=env)
    out = (p.stdout or "")
    err = (p.stderr or "")
    j = extract_json(out) or extract_json(err)
    if j is None:
        j = {"error": "no_json", "stdout": out.strip(), "stderr": err.strip()}
    return j

rows = []
for name, base in TOOLS:
    res = run(base)
    rows.append((name,
                 res.get("duration_s"),
                 res.get("energy_kwh"),
                 res.get("emissions_kg"),
                 res.get("error"),
                 (res.get("stderr") or res.get("stdout") or "")[:120]))

w = max(len(n) for n, *_ in rows)
print(f"{'tool'.ljust(w)}  duration_s            energy_kwh            emissions_kg           error/notes")
for n, d, e, c, err, note in rows:
    msg = err or note
    print(f"{n.ljust(w)}  {str(d).rjust(10)}   {str(e).rjust(12)}   {str(c).rjust(14)}   {msg}")
