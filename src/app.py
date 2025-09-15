from __future__ import annotations
import os, sys, tempfile, time, traceback, runpy, json, csv, subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional
import streamlit as st

# ────────────────────────────── Thème & Styles ──────────────────────────────
st.set_page_config(
    page_title="Green Assistant",
    page_icon="🌱",
    layout="centered",
    initial_sidebar_state="collapsed"   # sidebar fermée au départ
)

st.markdown(
    """
<style>
:root{
  --bg:#0e0e0e; --bg-2:#171616; --fg:#ffffff;
  --green:#205f2a; --green-2:#1b5123; --chip:#102114;
  --card:#121212; --card-b:#1e1e1e;
  --muted:#a6b0a4;
  --ok:#16a34a; --warn:#d97706; --bad:#ef4444;
}

/* Fond global + header */
[data-testid="stAppViewContainer"]{ background:var(--bg); color:var(--fg); }
[data-testid="stHeader"]{ background:var(--bg-2); }
[data-testid="stHeader"] *{ color:#e9efe7 !important; }

/* Sidebar */
section[data-testid="stSidebar"]{
  background:var(--bg-2);
  border-right:1px solid #111;
}
section[data-testid="stSidebar"] div[data-testid="stSidebarContent"]{
  min-height:100vh; display:flex; flex-direction:column; gap:12px;
  padding:12px 14px !important; box-sizing:border-box;
}

/* Titres & labels */
h1,h2,h3,h4{ color:var(--fg); letter-spacing:.2px; }
div[data-testid="stWidgetLabel"] > label p,
div[data-testid="stWidgetLabel"] > p,
.stTextArea label p, .stSelectbox label p, label { color:#fff !important; }

/* Select clair */
[data-testid="stSelectbox"] div[data-baseweb="select"] > div{ background:#eef1f5; color:#000; }
[data-testid="stSelectbox"] div[data-baseweb="select"] *{ color:#000 !important; }

/* Zone de code blanche */
.stTextArea textarea{
  background:#fff !important; color:#000 !important;
  font-family:"JetBrains Mono","Fira Code","SFMono-Regular",Menlo,Consolas,monospace !important;
  font-size:14px !important; line-height:1.45; border-radius:12px;
}
.stTextArea textarea::placeholder{ color:#000 !important; opacity:.6; }

/* Stat block (utilisé ailleurs) */
.stat{
  background:var(--card);
  border:1px solid var(--card-b);
  border-radius:12px;
  padding:14px; text-align:center;
}
.stat h3{ margin:.2rem 0 .4rem 0; font-weight:600; color:#dfe7dc; }
.stat .val{ font-size:1.2rem; color:#fff; }

/* Badge backend */
.badge{
  display:inline-block; padding:.2rem .6rem; border-radius:999px;
  border:1px solid #2a3b2a; background:var(--chip); color:#bfe8c1; font-size:.78rem;
}

/* Bouton Analyser */
.stButton{ display:flex; justify-content:center; }
.stButton > button{
  width:200px !important; background:var(--green) !important; color:#fff !important;
  border:none; border-radius:14px; padding:.60rem 1.2rem; margin:12px auto !important;
  box-shadow:0 6px 18px rgba(0,0,0,.35); font-weight:700; letter-spacing:.2px;
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
.tool-ct{ background:#0f1c26; color:#b8eaff; border-color:#1c5a78;}
.tool-e2{ background:#241229; color:#f1c8ff; border-color:#6a1e7a;}
.tool-tr{ background:#26170f; color:#ffd1a6; border-color:#7a3a1c;}

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

/* ───────── carte Résultat compacte ───────── */
.result-wrap{
  margin: 6px 0 18px;
}
.result-card{
  background:var(--card);
  border:1px solid var(--card-b);
  border-radius:16px;
  padding:18px 20px;
  box-shadow:0 8px 24px rgba(0,0,0,.28);
}
.result-headline{
  font-size:1.8rem; font-weight:800; color:#fff; margin:0 0 12px;
}
.kpi-grid{
  display:grid; gap:12px;
  grid-template-columns: repeat(3, minmax(0,1fr));
}
.kpi{
  background:linear-gradient(180deg, #151515 0%, #0f0f0f 100%);
  border:1px solid rgba(255,255,255,.08);
  border-radius:14px; padding:16px; text-align:center;
}
.kpi h4{ margin:0 0 6px; font-weight:700; font-size:1.1rem; color:#e9efe7; }
.kpi .val{ font-size:1.1rem; color:#fff; }

.result-energies{
  margin-top:10px; color:#cfd7cc; font-size:.92rem;
}
.result-context{
  margin-top:6px; color:#aeb4ac; font-size:.88rem;
}
</style>
""",
    unsafe_allow_html=True,
)

# ───────────────────────────── Session / Historique ──────────────────────────
if "history" not in st.session_state:
    st.session_state["history"] = []
if "code_input" not in st.session_state:
    st.session_state["code_input"] = ""
if "tool_select" not in st.session_state:
    st.session_state["tool_select"] = "CodeCarbon"

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

def _fmt_s(val: Optional[float]) -> str:
    return _fmt_num(val, lambda v: f"{v:.2f} s")

def _fmt_kwh(val: Optional[float]) -> str:
    return _fmt_num(val, lambda v: f"{v:.3e} kWh")

def _fmt_g(val: Optional[float]) -> str:
    return _fmt_num(val, lambda v: f"{v:.3f} g")

def _co2_level(kg: Optional[float]) -> str:
    if kg is None: return "lv-ok"
    try:
        if kg >= 1e-2: return "lv-bad"
        if kg >= 1e-3: return "lv-warn"
        return "lv-ok"
    except Exception:
        return "lv-ok"

def _tool_chip_cls(tool: str) -> str:
    t = tool.lower()
    if "codecarbon" in t: return "tool-cc"
    if "carbontracker" in t: return "tool-ct"
    if "eco2ai" in t: return "tool-e2"
    if "tracarbon" in t: return "tool-tr"
    return ""

# ───────────────────── Détection & Recos (compact) ─────────────────────
def detect_language(code: str) -> str:
    import re
    if re.search(r"^\s*import\s+\w+", code, re.M) or re.search(r"\bdef\s+\w+\s*\(", code):
        return "python"
    if re.search(r"\bfunction\s+\w+\s*\(|=>\s*{", code):
        return "javascript"
    return "unknown"

def detect_frameworks_python(code: str) -> List[str]:
    libs = ["numpy", "pandas", "torch", "tensorflow", "requests", "multiprocessing"]
    import re
    return [lib for lib in libs if re.search(rf"\b(?:import|from)\s+{lib}\b", code)]

def _has_sleep_in_loop(code: str) -> bool:
    import re
    rg = re.compile(r"(^[ \t]*for\s+\w+\s+in\s+range\s*\([^)]*\):)([\s\S]*?)(?=^[^\s]|$)", re.M)
    for m in rg.finditer(code):
        if re.search(r"\n[ \t]+time\.sleep\s*\(", m.group(2)):
            return True
    return False

def detect_energy_smells_python(code: str) -> List[str]:
    import re
    smells: List[str] = []
    if _has_sleep_in_loop(code): smells.append("sleep_dans_boucle")
    if re.search(r"for\s+\w+\s+in\s+range\s*\([^)]*\):[\s\S]*?(?:open\(|read\(|write\()", code):
        smells.append("IO_dans_boucle")
    if re.search(r"for\s+\w+\s+in\s+range\s*\([^)]*\):[\s\S]*?\w+\s*\+=\s*['\"]", code):
        smells.append("concat_string_dans_boucle")
    if re.search(r"for[\s\S]*?for[\s\S]*?for|for[\s\S]*?for", code):
        smells.append("boucles_imbriquees")
    if re.search(r"\b(?:import|from)\s+numpy\b", code) and re.search(r"for\s+.*:\s*[\s\S]*\+=", code):
        smells.append("non_vectorise_alors_numpy_dispo")
    if re.search(r"requests\.(?:get|post|put|delete|patch|head)\(", code) and re.search(r"\bfor\s+", code):
        smells.append("requetes_repetitives_sequentielles")
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

# ──────────────────────── Mesures (4 backends) ────────────────────────
def _write_snippet(code: str) -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="code_")) / "snippet.py"
    tmp.write_text(code, encoding="utf-8")
    return tmp

def measure_with_codecarbon(code: str) -> Dict[str, Any]:
    try:
        from codecarbon import EmissionsTracker
    except Exception as e:
        return {"error":"codecarbon_missing","notes":"Installe : pip install codecarbon psutil","stderr":str(e)}
    out_dir = Path(tempfile.mkdtemp(prefix="cc_run_"))
    csv_path = out_dir / "emissions.csv"
    os.environ.setdefault("CODECARBON_LOG_LEVEL","error")
    tracker = EmissionsTracker(output_dir=str(out_dir), output_file="emissions.csv",
                               measure_power_secs=1, save_to_file=True, log_level="error")
    run_err, err_text, emissions_kg = False, "", None
    tmp = _write_snippet(code)
    try:
        tracker.start()
        try:
            runpy.run_path(str(tmp), run_name="__main__")
        except SystemExit:
            pass
        except Exception:
            run_err, err_text = True, traceback.format_exc()
        finally:
            emissions_kg = tracker.stop()
    finally:
        time.sleep(0.1)
        try: tmp.unlink(missing_ok=True)
        except Exception: pass

    res: Dict[str, Any] = {
        "duration_s": None, "energy_kwh": None,
        "cpu_energy_kwh": None, "gpu_energy_kwh": None, "ram_energy_kwh": None,
        "emissions_kg": float(emissions_kg) if emissions_kg is not None else None,
    }
    try:
        if csv_path.exists():
            with csv_path.open("r", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            if rows:
                last = rows[-1]
                def ffloat(x):
                    try: return float(x) if x not in (None,"","None") else None
                    except: return None
                res["duration_s"]    = ffloat(last.get("duration"))
                res["energy_kwh"]    = ffloat(last.get("energy_consumed"))
                res["cpu_energy_kwh"]= ffloat(last.get("cpu_energy"))
                res["gpu_energy_kwh"]= ffloat(last.get("gpu_energy"))
                res["ram_energy_kwh"]= ffloat(last.get("ram_energy"))
    except Exception:
        pass
    if run_err: res["run_error"]=True; res["stderr"]=err_text.strip()
    return res

def measure_with_carbontracker(code: str) -> Dict[str, Any]:
    try:
        from carbontracker.tracker import CarbonTracker
        from carbontracker import parser as ct_parser
    except Exception as e:
        return {"error":"carbontracker_missing","notes":"Installe : pip install carbontracker psutil nvidia-ml-py3","stderr":str(e)}
    log_dir = Path(tempfile.mkdtemp(prefix="ct_logs_"))
    tmp = _write_snippet(code)
    data: Dict[str, Any] = {"duration_s": None, "energy_kwh": None, "co2eq_g": None, "emissions_kg": None}
    run_err, err_text = False, ""
    try:
        tracker = CarbonTracker(epochs=1, monitor_epochs=1, epochs_before_pred=1,
                                update_interval=1, verbose=0, log_dir=str(log_dir), components="cpu")
        t0 = time.time()
        tracker.epoch_start()
        try:
            runpy.run_path(str(tmp), run_name="__main__")
        except SystemExit:
            pass
        except Exception:
            run_err, err_text = True, traceback.format_exc()
        finally:
            tracker.epoch_end(); tracker.stop()
            data["duration_s"] = time.time() - t0
    finally:
        time.sleep(0.15)
        try: tmp.unlink(missing_ok=True)
        except Exception: pass
    try:
        logs = ct_parser.parse_all_logs(str(log_dir)) or []
        if not logs and (log_dir / "carbontracker").exists():
            logs = ct_parser.parse_all_logs(str(log_dir / "carbontracker")) or []
        if not logs:
            home_default = Path.home() / ".carbontracker" / "logs"
            if home_default.exists():
                logs = ct_parser.parse_all_logs(str(home_default)) or []
        if logs:
            last = logs[-1]; actual = (last or {}).get("actual") or {}
            dur    = actual.get("duration (s)")
            energy = actual.get("energy (kWh)")
            co2g   = actual.get("co2eq (g)")
            if dur    is not None: data["duration_s"] = float(dur)
            if energy is not None: data["energy_kwh"] = float(energy)
            if co2g   is not None:
                data["co2eq_g"] = float(co2g)
                data["emissions_kg"] = data["co2eq_g"]/1000.0
    except Exception:
        pass
    if run_err: data["run_error"]=True; data["stderr"]=err_text.strip()
    return data

def measure_with_eco2ai(code: str) -> Dict[str, Any]:
    try:
        import eco2ai  # type: ignore
    except Exception as e:
        return {"error":"eco2ai_missing","notes":"Installe : pip install eco2ai psutil","stderr":str(e)}
    out_dir = Path(tempfile.mkdtemp(prefix="eco2ai_"))
    csv_path = out_dir / "emissions.csv"
    tmp = _write_snippet(code)
    data: Dict[str, Any] = {"duration_s": None, "energy_kwh": None, "co2eq_g": None, "emissions_kg": None, "country": None}
    tracker = eco2ai.Tracker(project_name="GreenAssistant", experiment_description="Eco2AI run", file_name=str(csv_path))
    run_err, err_text = False, ""
    try:
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
        try: tmp.unlink(missing_ok=True)
        except Exception: pass
    try:
        if csv_path.exists():
            with csv_path.open("r", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            if rows:
                last = rows[-1]
                def ffloat(x, default=None):
                    try: return float(x) if x not in (None,"","None") else default
                    except: return default
                data["duration_s"] = ffloat(last.get("duration(s)"))
                data["energy_kwh"] = ffloat(last.get("power_consumption(kWTh)"))
                co2_kg = ffloat(last.get("CO2_emissions(kg)"))
                data["emissions_kg"] = co2_kg
                data["co2eq_g"] = co2_kg*1000.0 if co2_kg is not None else None
                data["country"] = last.get("country") or None
    except Exception:
        pass
    if run_err: data["run_error"]=True; data["stderr"]=err_text.strip()
    return data

def measure_with_tracarbon_via_wrapper(code: str) -> Dict[str, Any]:
    here = Path(__file__).parent
    candidates = [here / "src" / "tracarbon-api.py", here / "tracarbon-api.py"]
    script = next((p for p in candidates if p.exists()), None)
    if not script:
        return {"error":"tracarbon_wrapper_missing",
                "notes":"Wrapper tracarbon-api.py introuvable. Place-le dans ./src/ ou à côté de app.py."}
    tmp = _write_snippet(code)
    try:
        p = subprocess.run([sys.executable, str(script), str(tmp)],
                           capture_output=True, text=True, timeout=180)
    except Exception as e:
        try: tmp.unlink(missing_ok=True)
        except Exception: pass
        return {"error":"tracarbon_wrapper_failed","notes":str(e)}
    finally:
        try: tmp.unlink(missing_ok=True)
        except Exception: pass
    out = (p.stdout or "").strip()
    try:
        payload = json.loads(out)
        return payload if isinstance(payload, dict) else {"error":"tracarbon_invalid_json","notes":out[:400]}
    except Exception:
        return {"error":"tracarbon_no_json","notes":(p.stderr or out)[:400]}

# ───────────────────────────── UI ─────────────────────────────
st.title("Green Assistant")

tool = st.selectbox(
    "Choisissez l’outil de mesure :",
    ["CodeCarbon", "CarbonTracker", "Eco2AI", "Tracarbon"],
    index=["CodeCarbon","CarbonTracker","Eco2AI","Tracarbon"].index(st.session_state["tool_select"]),
    key="tool_select",
)
st.markdown(f'<span class="badge">Backend sélectionné : {tool}</span>', unsafe_allow_html=True)

code = st.text_area(
    "Collez ici votre code :",
    height=260,
    key="code_input",
    placeholder="Collez ici votre code",
    help="Le code est exécuté tel quel dans l’environnement local (même interpréteur que Streamlit).",
)

left, center, right = st.columns([1, 1, 1])
with center:
    run_btn = st.button("Analyser", type="primary")

# ───────────────────────────── Affichage du résultat ─────────────────────────────
def render_result(res: Dict[str, Any]) -> None:
    kg = res.get("emissions_kg")
    co2g = res.get("co2eq_g")
    duration = res.get("duration_s")
    energy = res.get("energy_kwh")
    cpu = res.get("cpu_energy_kwh")
    gpu = res.get("gpu_energy_kwh")
    ram = res.get("ram_energy_kwh")

    # Headline en kg (prend emissions_kg si dispo, sinon convertit co2eq_g)
    if isinstance(kg, (int, float)):
        headline = _co2_fmt_kg(kg)
    elif isinstance(co2g, (int, float)):
        headline = _co2_fmt_kg(co2g / 1000.0)
    else:
        headline = "Empreinte : indisponible"

    # Valeur CO2eq g
    if isinstance(co2g, (int, float)):
        co2_g_txt = _fmt_g(co2g)
    elif isinstance(kg, (int, float)):
        co2_g_txt = _fmt_g(kg * 1000.0)
    else:
        co2_g_txt = "—"

    duration_txt = _fmt_s(duration)
    energy_txt = _fmt_kwh(energy)

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
<div class="result-wrap">
  <div class="result-card">
    <div class="result-headline">{headline}</div>
    <div class="kpi-grid">
      <div class="kpi"><h4>Durée</h4><div class="val">{duration_txt}</div></div>
      <div class="kpi"><h4>Énergie</h4><div class="val">{energy_txt}</div></div>
      <div class="kpi"><h4>CO₂eq</h4><div class="val">{co2_g_txt}</div></div>
    </div>
    {extras_html}
    {ctx_html}
  </div>
</div>
""", unsafe_allow_html=True)

# ───────────────────────────── Traitement ─────────────────────────────
if run_btn:
    lang = detect_language(code)
    fw = detect_frameworks_python(code) if lang == "python" else []
    smells = detect_energy_smells_python(code) if lang == "python" else []
    recos = suggestions_for(smells, fw)

    with st.spinner("Mesure en cours…"):
        if tool == "CodeCarbon":
            res = measure_with_codecarbon(code)
        elif tool == "CarbonTracker":
            res = measure_with_carbontracker(code)
        elif tool == "Eco2AI":
            res = measure_with_eco2ai(code)
        else:
            res = measure_with_tracarbon_via_wrapper(code)

    st.session_state["history"].append({
        "tool": tool,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "code": code,
        "res": res,
    })

    if "error" in res:
        st.error(res.get("notes") or f"Erreur {res.get('error')}")
        if res.get("stderr"):
            with st.expander("Détails de l’erreur"):
                st.code(res["stderr"])
    else:
        st.subheader("Résultat")
        render_result(res)  # <<< NOUVEAU FORMAT
        st.markdown("### Analyse du code")
        st.write(f"**Langage :** {lang}")
        st.write(f"**Frameworks :** {', '.join(fw) if fw else '—'}")
        st.write("**Motifs énergivores détectés :** " + (", ".join(smells) if smells else "—"))

        st.markdown("### Recommandations")
        if recos:
            for r in recos:
                st.markdown(f"- {r}")
        else:
            st.markdown("- Aucune recommandation détectée.")

# ───────────────────────────── Barre latérale ────────────────────────────────
with st.sidebar:
    st.markdown('<div class="sidebar-logo">🌱</div>', unsafe_allow_html=True)
    st.markdown('<div class="sidebar-title">Historique</div>', unsafe_allow_html=True)

    hist = st.session_state["history"]
    if not hist:
        st.markdown('<div class="history-empty">Aucun Run pour le moment.</div>', unsafe_allow_html=True)
    else:
        for h in reversed(hist):  # plus récents en haut
            tool = h.get("tool", "?")
            res  = h.get("res", {}) or {}
            kg   = res.get("emissions_kg")
            co2_txt = _co2_fmt_kg(kg) if isinstance(kg, (int,float)) else "—"
            level = _co2_level(kg if isinstance(kg,(int,float)) else None)
            ts    = h.get("timestamp", "")
            dur   = res.get("duration_s")
            en    = res.get("energy_kwh")
            dur_txt = _fmt_s(dur)
            en_txt  = _fmt_kwh(en)
            code_prev = _short_code_preview(h.get("code",""))

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
