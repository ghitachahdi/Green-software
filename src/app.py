from __future__ import annotations
import os, sys, tempfile, time, traceback, runpy, json, csv, subprocess, re
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import streamlit as st

# ────────────────────────────── Thème & Styles ──────────────────────────────
st.set_page_config(page_title="Green Assistant", page_icon="🌱", layout="centered", initial_sidebar_state="collapsed")
st.markdown("""
<style>
:root{ --bg:#0e0e0e; --bg-2:#171616; --fg:#ffffff; --green:#205f2a; --green-2:#1b5123; --chip:#102114;
       --card:#121212; --card-b:#1e1e1e; --muted:#a6b0a4; --ok:#16a34a; --warn:#d97706; --bad:#ef4444; }
[data-testid="stAppViewContainer"]{ background:var(--bg); color:var(--fg); }
[data-testid="stHeader"]{ background:var(--bg-2); } [data-testid="stHeader"] *{ color:#e9efe7 !important; }
section[data-testid="stSidebar"]{ background:var(--bg-2); border-right:1px solid #111; }
section[data-testid="stSidebar"] div[data-testid="stSidebarContent"]{ min-height:100vh; display:flex; flex-direction:column; gap:12px; padding:12px 14px !important; }
h1,h2,h3,h4{ color:var(--fg); letter-spacing:.2px; }
div[data-testid="stWidgetLabel"] > label p, .stTextArea label p, .stSelectbox label p, label { color:#fff !important; }

/* Zones côte à côte */
.section-card{ background:var(--card); border:1px solid var(--card-b); border-radius:16px; padding:18px 20px; box-shadow:0 8px 24px rgba(0,0,0,.28); }

/* Champs code blancs */
.stTextArea textarea{
  background:#fff !important; color:#000 !important;
  font-family:"JetBrains Mono","Fira Code","SFMono-Regular",Menlo,Consolas,monospace !important;
  font-size:14px !important; line-height:1.45; border-radius:12px;
}

/* Boutons verts (tous) */
.stButton{ display:flex; justify-content:center; }
.stButton > button{
  min-width:200px !important; background:var(--green) !important; color:#fff !important;
  border:none; border-radius:14px; padding:.60rem 1.2rem; box-shadow:0 6px 18px rgba(0,0,0,.35);
  font-weight:700; letter-spacing:.2px;
}
.stButton > button:hover{ background:var(--green-2) !important; }

/* Logo + Titre (sidebar) */
.sidebar-logo{
  position:relative; display:flex; justify-content:center; align-items:center;
  font-size:52px; line-height:1;
  filter:drop-shadow(0 4px 10px rgba(0,0,0,.35));
  padding-bottom:14px; margin-bottom:20px !important;
}
.sidebar-logo::after{
  content:""; position:absolute; left:8px; right:8px; bottom:0;
  height:2px; border-radius:999px;
  background:linear-gradient(90deg,transparent,rgba(255,255,255,.5),transparent);
}
.sidebar-title{
  width:100%; text-align:center; font-weight:800; font-size:1.05rem; color:#eaf3ea;
  letter-spacing:.2px; margin:0 0 15px 0 !important;
}

/* Historique — cartes */
.history-empty{
  color:var(--muted); text-align:center; padding:6px 0 2px; font-size:.95rem;
}
.history-card{
  position:relative; border-radius:14px; padding:10px 12px;
  background:linear-gradient(180deg, #151515 0%, #0f0f0f 100%);
  border:1px solid rgba(255,255,255,.06);
  box-shadow:0 8px 22px rgba(0,0,0,.25);
  transition:transform .15s ease, box-shadow .15s ease, border-color .15s ease;
}
.history-card:hover{
  transform:translateY(-1px);
  box-shadow:0 12px 26px rgba(0,0,0,.35);
  border-color:rgba(255,255,255,.14);
}
.hdr{ display:flex; justify-content:space-between; align-items:center; gap:10px; margin-bottom:6px; }
.chip{
  display:inline-flex; align-items:center; gap:6px;
  padding:.18rem .55rem; border-radius:999px; font-size:.78rem; font-weight:700;
  border:1px solid rgba(255,255,255,.12);
}
.tool-cc{ background:#0f2a18; color:#b7f4c4; border-color:#1e5e36;}
.tool-e2{ background:#241229; color:#f1c8ff; border-color:#6a1e7a;}

.badge-co2{
  padding:.22rem .55rem; border-radius:999px; font-weight:800; font-size:.80rem;
  background:#1a1a1a; border:1px solid rgba(255,255,255,.12);
}
.lv-ok{   color:#86efac; border-color:#234f2b; background:#102115;}
.lv-warn{ color:#fbbf24; border-color:#4f3b1a; background:#211a10;}
.lv-bad{  color:#fca5a5; border-color:#5a1e1e; background:#210f10;}

/* Code preview & meta */
.code-preview{
  color:#d7dbd5; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace;
  font-size:.82rem; line-height:1.35; opacity:.95; margin:2px 0 8px;
  display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden;
}
.meta{
  display:flex; gap:10px; flex-wrap:wrap; color:#aeb4ac; font-size:.8rem;
}
.meta .pill{
  background:#0f0f0f; border:1px solid rgba(255,255,255,.08);
  border-radius:8px; padding:.2rem .45rem; color:#cfd7cc;
}

/* Carte résultat */
.result-wrap{ margin: 8px 0 18px; }
.result-card{ background:var(--card); border:1px solid var(--card-b); border-radius:16px; padding:18px 20px; box-shadow:0 8px 24px rgba(0,0,0,.28); }
.result-headline{ font-size:1.8rem; font-weight:800; color:#fff; margin:0 0 12px; }
.kpi-grid{ display:grid; gap:12px; grid-template-columns: repeat(3, minmax(0,1fr)); }
.kpi{ background:linear-gradient(180deg,#151515 0%,#0f0f0f 100%); border:1px solid rgba(255,255,255,.08); border-radius:14px; padding:16px; text-align:center; }
.kpi h4{ margin:0 0 6px; font-weight:700; font-size:1.1rem; color:#e9efe7; }
.kpi .val{ font-size:1.1rem; color:#fff; }
.result-energies{ margin-top:10px; color:#cfd7cc; font-size:.92rem; }
.result-context{ margin-top:6px; color:#aeb4ac; font-size:.88rem; }
</style>
""", unsafe_allow_html=True)

# ───────────────────────────── Session ─────────────────────────────
ss = st.session_state
ss.setdefault("history", [])
ss.setdefault("tool_select", "CodeCarbon")
ss.setdefault("code_input_analyse", "")
ss.setdefault("code_input_generate", "")
ss.setdefault("generated_code", "")
ss.setdefault("rag_sources", [])

# ───────────────────────────── Utils ─────────────────────────────
def _short_code_preview(code: str, n=160) -> str:
    code1 = (code or "").strip().replace("\n", " ")
    return (code1[:n] + "…") if len(code1) > n else code1

def _fmt_num(x: Optional[float], f=None) -> str:
    if x is None: return "—"
    try: return f(x) if f else str(x)
    except Exception: return str(x)

def _co2_fmt_kg(kg: Optional[float]) -> str:
    if kg is None: return "—"
    if 0 < kg < 1e-5: return f"{kg:.2e} kgCO₂"
    return f"{kg:.5f} kgCO₂"

def _fmt_s(v: Optional[float]) -> str: return _fmt_num(v, lambda x: f"{x:.2f} s")
def _fmt_kwh(v: Optional[float]) -> str: return _fmt_num(v, lambda x: f"{x:.3e} kWh")
def _fmt_g(v: Optional[float]) -> str: return _fmt_num(v, lambda x: f"{x:.3f} g")

def _co2_level(kg: Optional[float]) -> str:
    if kg is None: return "lv-ok"
    if kg >= 1e-2: return "lv-bad"
    if kg >= 1e-3: return "lv-warn"
    return "lv-ok"

def _tool_chip_cls(tool: str) -> str:
    t = tool.lower()
    if "codecarbon" in t: return "tool-cc"
    if "eco2ai" in t: return "tool-e2"
    return ""

# ───────────────────── Détection & Recos ─────────────────────
def detect_language(code: str) -> str:
    if re.search(r"^\s*import\s+\w+", code, re.M) or re.search(r"\bdef\s+\w+\s*\(", code): return "python"
    if re.search(r"\bfunction\s+\w+\s*\(|=>\s*{", code): return "javascript"
    return "unknown"

def detect_frameworks_python(code: str) -> List[str]:
    libs = ["numpy", "pandas", "torch", "tensorflow", "requests", "multiprocessing", "asyncio"]
    return [lib for lib in libs if re.search(rf"\b(?:import|from)\s+{lib}\b", code)]

def _has_sleep_in_loop(code: str) -> bool:
    rg = re.compile(r"(^[ \t]*for\s+\w+\s+in\s+range\s*\([^)]*\):)([\s\S]*?)(?=^[^\s]|$)", re.M)
    for m in rg.finditer(code):
        if re.search(r"\n[ \t]+time\.sleep\s*\(", m.group(2)): return True
    return False

def detect_energy_smells_python(code: str) -> List[str]:
    smells: List[str] = []
    if _has_sleep_in_loop(code): smells.append("sleep_dans_boucle")
    if re.search(r"for\s+\w+\s+in\s+range\s*\([^)]*\):[\s\S]*?(?:open\(|read\(|write\()", code): smells.append("IO_dans_boucle")
    if re.search(r"for\s+\w+\s+in\s+range\s*\([^)]*\):[\s\S]*?\w+\s*\+=\s*['\"]", code): smells.append("concat_string_dans_boucle")
    if re.search(r"for[\s\S]*?for[\s\S]*?for|for[\s\S]*?for", code): smells.append("boucles_imbriquees")
    if re.search(r"\b(?:import|from)\s+numpy\b", code) and re.search(r"for\s+.*:\s*[\s\S]*\+=", code): smells.append("non_vectorise_alors_numpy_dispo")
    if re.search(r"requests\.(?:get|post|put|delete|patch|head)\(", code) and re.search(r"\bfor\s+", code): smells.append("requetes_repetitives_sequentielles")
    return smells

def suggestions_for(smells: List[str], frameworks: List[str]) -> List[str]:
    s: List[str] = []
    if "non_vectorise_alors_numpy_dispo" in smells: s.append("Vectoriser avec NumPy (np.dot, np.sum, broadcasting).")
    if "sleep_dans_boucle" in smells: s.append("Éviter time.sleep() dans les boucles ; utiliser un scheduler/événements.")
    if "IO_dans_boucle" in smells: s.append("Regrouper les I/O hors boucle (bufferisation, lecture/écriture en bloc).")
    if "concat_string_dans_boucle" in smells: s.append("Utiliser ''.join() ou io.StringIO plutôt que s += ... en boucle.")
    if "requetes_repetitives_sequentielles" in smells: s.append("Mutualiser (requests.Session) + paralléliser (asyncio/threading) avec throttling.")
    if "pandas" in frameworks: s.append("Préférer les opérations Pandas vectorisées à apply/itertuples.")
    return s

# ───────────── RAG local (patterns + réécriture prudente) ─────────────
class GreenPattern:
    def __init__(self, pid: str, title: str, smell: Optional[str], keywords: List[str], template_hint: str):
        self.pid = pid; self.title = title; self.smell = smell; self.keywords = keywords; self.template_hint = template_hint

GREEN_PATTERNS: List[GreenPattern] = [
    GreenPattern("P001","Concaténation en boucle ➜ join()/StringIO","concat_string_dans_boucle",
                 ["+=", "string", "boucle", "for", "concat"], "Remplacer s += ... par ''.join(parts)."),
    GreenPattern("P002","HTTP répétitives ➜ Session + parallélisme","requetes_repetitives_sequentielles",
                 ["requests.get","for","http","url","session"], "Session + ThreadPoolExecutor / asyncio."),
    GreenPattern("P003","I/O dans boucle ➜ bufferisation","IO_dans_boucle",
                 ["open(","read(","write(","for"], "open() hors boucle + écriture en bloc."),
    GreenPattern("P004","sleep() en boucle ➜ scheduler/backoff","sleep_dans_boucle",
                 ["time.sleep(","for","polling"], "Scheduler, events, backoff exponentiel."),
    GreenPattern("P005","NumPy dispo ➜ vectorisation","non_vectorise_alors_numpy_dispo",
                 ["numpy","for","+=","array"], "Remplacer boucles par opérations vectorisées."),
]

def retrieve_patterns(code: str, smells: List[str], top_k: int = 3) -> List[GreenPattern]:
    scored: List[Tuple[float, GreenPattern]] = []
    code_l = code.lower()
    for p in GREEN_PATTERNS:
        score = (2.0 if (p.smell and p.smell in smells) else 0.0) + sum(1 for kw in p.keywords if kw.lower() in code_l)
        if score > 0: scored.append((score, p))
    scored.sort(key=lambda t: t[0], reverse=True)
    return [p for _, p in scored[:top_k]]

def _rewrite_concat_in_loop(code: str) -> Tuple[str, bool]:
    changed = False; out = code
    loop_rg = re.compile(r"(^[ \t]*for\s+[^\n]+:\n)([\s\S]*?)(?=^[^\s]|$(?!\n))", re.M)
    for m in list(loop_rg.finditer(out)):
        loop_header, loop_body = m.group(1), m.group(2)
        concat_rg = re.compile(r"^[ \t]*([A-Za-z_]\w*)\s*\+=\s*(.+)$", re.M)
        candidates = list(concat_rg.finditer(loop_body))
        if not candidates: continue
        var = candidates[0].group(1); parts_name = f"_parts_{var}"
        new_body = concat_rg.sub(lambda mm: f"{' ' * (len(mm.group(0)) - len(mm.group(0).lstrip()))}{parts_name}.append({mm.group(2).strip()})", loop_body)
        before, after = out[:m.start()], out[m.end():]
        indent = re.match(r"^([ \t]*)", loop_header).group(1)
        init_line = f"{indent}{parts_name} = []\n"
        join_line = f"\n{indent}{var} = ''.join({parts_name})\n"
        out = before + init_line + loop_header + new_body + join_line + after
        changed = True
        return out, changed
    return out, changed

def _rewrite_requests_parallel(code: str) -> Tuple[str, bool]:
    if "requests." not in code or "for " not in code: return code, False
    tpl = r'''
# ───────────────────────── Code optimisé : HTTP en parallèle ─────────────────────────
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
def _fetch(session: requests.Session, url: str, timeout: float = 10.0):
    with session.get(url, timeout=timeout) as r:
        r.raise_for_status()
        return r.text
def fetch_all(urls: list[str], max_workers: int = 8):
    results = {}
    with requests.Session() as session:
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futs = {ex.submit(_fetch, session, u): u for u in urls}
            for fut in as_completed(futs):
                u = futs[fut]
                try: results[u] = fut.result()
                except Exception as e: results[u] = f"ERROR: {e}"
    return results
# Exemple: data_by_url = fetch_all(URLS, max_workers=8)
'''
    if tpl.strip() in code: return code, False
    return (code.rstrip() + "\n\n" + tpl.strip() + "\n"), True

def _append_note(code: str, text_block: str) -> Tuple[str, bool]:
    if text_block.strip() in code: return code, False
    return (code.rstrip() + "\n\n" + text_block.strip() + "\n"), True

def greenify_code(code: str, smells: List[str], lang: str) -> Tuple[str, List[str]]:
    applied: List[str] = []; out = code
    if lang == "python":
        if "concat_string_dans_boucle" in smells:
            out, ok = _rewrite_concat_in_loop(out);  applied += ["P001: Concat ➜ join()"] if ok else []
        if "requetes_repetitives_sequentielles" in smells:
            out, ok = _rewrite_requests_parallel(out); applied += ["P002: Session + ThreadPoolExecutor"] if ok else []
        if "IO_dans_boucle" in smells:
            tip = "# Astuce green : I/O hors des boucles → bufferiser et écrire en bloc."
            out, ok = _append_note(out, tip); applied += ["P003: I/O hors boucle (note)"] if ok else []
        if "sleep_dans_boucle" in smells:
            tip = "# Note : éviter time.sleep() en boucle → scheduler / events / backoff."
            out, ok = _append_note(out, tip); applied += ["P004: sleep ➜ scheduler/backoff (note)"] if ok else []
        if "non_vectorise_alors_numpy_dispo" in smells:
            tip = "# Astuce : Vectorisation NumPy (remplacer boucles par opérations vectorisées)."
            out, ok = _append_note(out, tip); applied += ["P005: Vectorisation NumPy (note)"] if ok else []
    return out, applied

# ──────────────────────── Mesures (2 backends actifs) ────────────────────────
def _write_snippet(code: str) -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="code_")) / "snippet.py"; tmp.write_text(code, encoding="utf-8"); return tmp

def measure_with_codecarbon(code: str) -> Dict[str, Any]:
    try: from codecarbon import EmissionsTracker
    except Exception as e: return {"error":"codecarbon_missing","notes":"Installe : pip install codecarbon psutil","stderr":str(e)}
    out_dir = Path(tempfile.mkdtemp(prefix="cc_run_")); csv_path = out_dir / "emissions.csv"
    os.environ.setdefault("CODECARBON_LOG_LEVEL","error")
    tracker = EmissionsTracker(output_dir=str(out_dir), output_file="emissions.csv", measure_power_secs=1, save_to_file=True, log_level="error")
    run_err, err_text, emissions_kg = False, "", None; tmp = _write_snippet(code)
    try:
        tracker.start()
        try: runpy.run_path(str(tmp), run_name="__main__")
        except SystemExit: pass
        except Exception: run_err, err_text = True, traceback.format_exc()
        finally: emissions_kg = tracker.stop()
    finally:
        time.sleep(0.1)
        try: tmp.unlink(missing_ok=True)
        except Exception: pass
    res = {"duration_s": None, "energy_kwh": None, "cpu_energy_kwh": None, "gpu_energy_kwh": None, "ram_energy_kwh": None,
           "emissions_kg": float(emissions_kg) if emissions_kg is not None else None}
    try:
        if csv_path.exists():
            with csv_path.open("r", encoding="utf-8") as f: rows = list(csv.DictReader(f))
            if rows:
                last = rows[-1]
                def ffloat(x): 
                    try: return float(x) if x not in (None,"","None") else None
                    except: return None
                res["duration_s"]     = ffloat(last.get("duration"))
                res["energy_kwh"]     = ffloat(last.get("energy_consumed"))
                res["cpu_energy_kwh"] = ffloat(last.get("cpu_energy"))
                res["gpu_energy_kwh"] = ffloat(last.get("gpu_energy"))
                res["ram_energy_kwh"] = ffloat(last.get("ram_energy"))
    except Exception: pass
    if run_err: res["run_error"]=True; res["stderr"]=err_text.strip()
    return res

def measure_with_eco2ai(code: str) -> Dict[str, Any]:
    try:
        import eco2ai  # type: ignore
    except Exception as e:
        return {"error": "eco2ai_missing", "notes": "Installe : pip install eco2ai psutil", "stderr": str(e)}

    import os, tempfile, csv, traceback, runpy
    from pathlib import Path

    # Dossier pour le CSV (écriture autorisée)
    out_dir = Path(tempfile.mkdtemp(prefix="eco2ai_"))
    csv_path = out_dir / "emissions.csv"

    # Dossier temporaire pour le params.json d’Eco2AI (écriture autorisée)
    params_dir = Path(tempfile.mkdtemp(prefix="eco2ai_params_"))

    # Écrire le snippet à exécuter
    tmp = Path(tempfile.mkdtemp(prefix="code_")) / "snippet.py"
    tmp.write_text(code, encoding="utf-8")

    data: Dict[str, Any] = {
        "duration_s": None, "energy_kwh": None,
        "co2eq_g": None, "emissions_kg": None, "country": None
    }

    run_err, err_text = False, ""
    cwd = os.getcwd()
    try:
        # ⚠️ On se place dans un dossier en écriture le temps de créer/stopper le tracker
        os.chdir(params_dir)
        tracker = eco2ai.Tracker(
            project_name="GreenAssistant",
            experiment_description="Eco2AI run",
            file_name=str(csv_path)  # chemin du CSV dans /tmp
        )
        tracker.start()
        try:
            runpy.run_path(str(tmp), run_name="__main__")
        except SystemExit:
            pass
        except Exception:
            run_err, err_text = True, traceback.format_exc()
        finally:
            tracker.stop()
    finally:
        # On revient au répertoire initial
        try: os.chdir(cwd)
        except Exception: pass
        try: tmp.unlink(missing_ok=True)
        except Exception: pass

    # Lecture des résultats
    try:
        if csv_path.exists():
            with csv_path.open("r", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            if rows:
                last = rows[-1]
                def ffloat(x, default=None):
                    try:
                        return float(x) if x not in (None, "", "None") else default
                    except:
                        return default
                data["duration_s"] = ffloat(last.get("duration(s)"))
                data["energy_kwh"] = ffloat(last.get("power_consumption(kWTh)"))
                co2_kg = ffloat(last.get("CO2_emissions(kg)"))
                data["emissions_kg"] = co2_kg
                data["co2eq_g"] = co2_kg * 1000.0 if co2_kg is not None else None
                data["country"] = last.get("country") or None
    except Exception:
        pass

    if run_err:
        data["run_error"] = True
        data["stderr"] = err_text.strip()
    return data

# ───────────────────────────── UI ─────────────────────────────
st.title("Green Assistant")

# 2 zones côte à côte
left, right = st.columns(2, gap="large")

with left:
    TOOL_OPTIONS = ["CodeCarbon", "Eco2AI"]
    tool = st.selectbox(
        "Choisissez l’outil de mesure :",
        TOOL_OPTIONS,
        index=TOOL_OPTIONS.index(ss["tool_select"]) if ss.get("tool_select") in TOOL_OPTIONS else 0,
        key="tool_select",
    )
    st.markdown(f'<span class="badge">Backend sélectionné : {tool}</span>', unsafe_allow_html=True)
    code_to_analyse = st.text_area(
        "Code non green à analyser:",
        height=260,
        key="code_input_analyse",
        placeholder="Collez ici votre code"
    )
    run_btn = st.button("Analyser", key="btn_analyser")
    st.markdown('</div>', unsafe_allow_html=True)

with right:
    code_to_generate = st.text_area(
        "Code non green pour génération:",
        height=385,
        key="code_input_generate",
        placeholder="Collez ici votre code"
    )
    gen_btn = st.button("Générer", key="btn_generer")
    st.markdown('</div>', unsafe_allow_html=True)

# ───────────────────────────── Résultats ─────────────────────────────
def render_result(res: Dict[str, Any]) -> None:
    kg = res.get("emissions_kg"); co2g = res.get("co2eq_g")
    duration = res.get("duration_s"); energy = res.get("energy_kwh")
    cpu = res.get("cpu_energy_kwh"); gpu = res.get("gpu_energy_kwh"); ram = res.get("ram_energy_kwh")
    headline = _co2_fmt_kg(kg) if isinstance(kg, (int,float)) else (_co2_fmt_kg(co2g/1000.0) if isinstance(co2g,(int,float)) else "Empreinte : indisponible")
    co2_g_txt = _fmt_g(co2g) if isinstance(co2g,(int,float)) else (_fmt_g(kg*1000.0) if isinstance(kg,(int,float)) else "—")
    duration_txt = _fmt_s(duration); energy_txt = _fmt_kwh(energy)
    extras = []
    if isinstance(cpu, (int, float)): extras.append(f"CPU&nbsp;: {cpu:.3e} kWh")
    if isinstance(gpu, (int, float)): extras.append(f"GPU&nbsp;: {gpu:.3e} kWh")
    if isinstance(ram, (int, float)): extras.append(f"RAM&nbsp;: {ram:.3e} kWh")
    extras_html = f'<div class="result-energies">Détails énergie&nbsp;: ' + " · ".join(extras) + "</div>" if extras else ""
    ctx = []
    for k in ["country","region","cloud_provider","provider","regions"]:
        if res.get(k): ctx.append(f"{k}: {res[k]}")
    ctx_html = f'<div class="result-context">Contexte&nbsp;: ' + " | ".join(ctx) + "</div>" if ctx else ""
    st.markdown(f"""
<div class="result-wrap"><div class="result-card">
  <div class="result-headline">{headline}</div>
  <div class="kpi-grid">
    <div class="kpi"><h4>Durée</h4><div class="val">{duration_txt}</div></div>
    <div class="kpi"><h4>Énergie</h4><div class="val">{energy_txt}</div></div>
    <div class="kpi"><h4>CO₂eq</h4><div class="val">{co2_g_txt}</div></div>
  </div>
  {extras_html}{ctx_html}
</div></div>""", unsafe_allow_html=True)

# Analyse
if run_btn and code_to_analyse.strip():
    lang = detect_language(code_to_analyse)
    fw = detect_frameworks_python(code_to_analyse) if lang == "python" else []
    smells = detect_energy_smells_python(code_to_analyse) if lang == "python" else []
    recos = suggestions_for(smells, fw)

    with st.spinner("Mesure en cours…"):
        if tool == "CodeCarbon":
            res = measure_with_codecarbon(code_to_analyse)
        elif tool == "Eco2AI":
            res = measure_with_eco2ai(code_to_analyse)
        else:
            res = {"error":"unsupported_tool","notes":"Outil non pris en charge."}

    ss["history"].append({"tool": tool, "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"), "code": code_to_analyse, "res": res})

    st.subheader("Résultat d’analyse")
    if "error" in res:
        st.error(res.get("notes") or f"Erreur {res.get('error')}")
        if res.get("stderr"):
            with st.expander("Détails de l’erreur"): st.code(res["stderr"])
    else:
        render_result(res)
        st.markdown("### Analyse du code")
        st.write(f"**Langage :** {lang}")
        st.write(f"**Frameworks :** {', '.join(fw) if fw else '—'}")
        st.write("**Motifs énergivores détectés :** " + (", ".join(smells) if smells else "—"))
        st.markdown("### Recommandations")
        if recos: 
            for r in recos: st.markdown(f"- {r}")
        else:
            st.markdown("- Aucune recommandation détectée.")

# Génération
if gen_btn and code_to_generate.strip():
    lang = detect_language(code_to_generate)
    smells = detect_energy_smells_python(code_to_generate) if lang == "python" else []
    sources = retrieve_patterns(code_to_generate, smells, top_k=4)
    green_code, applied = greenify_code(code_to_generate, smells, lang)
    ss["generated_code"] = green_code
    ss["rag_sources"] = [f"{p.pid} — {p.title}" for p in sources]

    st.subheader("Code green généré (proposition)")
    st.code(green_code, language="python" if lang == "python" else None)
    st.download_button("Télécharger le code optimisé",
        data=green_code,
        file_name="green_code_optimized.py" if lang == "python" else "green_code_optimized.txt",
        mime="text/plain"
    )
    st.markdown("### Patterns RAG sélectionnés")
    if sources:
        for s in ss["rag_sources"]: st.markdown(f"- {s}")
    else:
        st.markdown("- Aucun pattern pertinent.")
    if applied:
        st.markdown("### Transformations appliquées")
        for a in applied: st.markdown(f"- {a}")
    else:
        st.info("Pas de transformation sûre appliquée — des notes/templates ont été ajoutés si utile.")

# ───────────────────────────── Barre latérale ────────────────────────────────
with st.sidebar:
    st.markdown('<div class="sidebar-logo">🌱</div>', unsafe_allow_html=True)
    st.markdown('<div class="sidebar-title">Historique</div>', unsafe_allow_html=True)
    hist = ss["history"]
    if not hist:
        st.markdown('<div class="history-empty">Aucun Run pour le moment.</div>', unsafe_allow_html=True)
    else:
        for h in reversed(hist):
            tool = h.get("tool", "?"); res = h.get("res", {}) or {}
            kg = res.get("emissions_kg"); co2_txt = _co2_fmt_kg(kg) if isinstance(kg,(int,float)) else "—"
            level = _co2_level(kg if isinstance(kg,(int,float)) else None)
            ts = h.get("timestamp",""); dur = res.get("duration_s"); en = res.get("energy_kwh")
            dur_txt = _fmt_s(dur); en_txt = _fmt_kwh(en); code_prev = _short_code_preview(h.get("code",""))
            st.markdown(f"""
<div class="history-card">
  <div class="hdr">
    <span class="chip {_tool_chip_cls(tool)}">{tool}</span>
    <span class="badge-co2 {level}">{co2_txt}</span>
  </div>
  <div class="code-preview">{code_prev}</div>
  <div class="meta">
    <span class="pill">Durée&nbsp;: {dur_txt}</span>
    <span class="pill">Énergie&nbsp;: {en_txt}</span>
    <span class="pill">{ts}</span>
  </div>
</div>
""", unsafe_allow_html=True)
