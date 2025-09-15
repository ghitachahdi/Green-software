import sys, os, csv, json, tempfile, traceback, runpy, logging, warnings
from pathlib import Path
import eco2ai

# calmer logs
logging.basicConfig(level=logging.CRITICAL)
warnings.filterwarnings("ignore")

def _ffloat(x, default=None):
    try:
        return float(x) if x not in (None, "", "None") else default
    except Exception:
        return default

def _pick(row: dict, *names):
    for n in names:
        if n in row and row[n] not in (None, "", "None"):
            return row[n]
    return None

def run_and_track_file(code_file: str) -> dict:
    out_dir = Path(tempfile.mkdtemp(prefix="eco2ai_"))
    csv_path = out_dir / "emissions.csv"
    tracker = eco2ai.Tracker(project_name="GreenAssistant",
                             experiment_description="VSCode Eco2AI run",
                             file_name=str(csv_path))
    run_error, err_text = False, ""
    tracker.start()
    try:
        runpy.run_path(code_file, run_name="__main__")
    except SystemExit:
        pass
    except Exception:
        run_error = True
        err_text = traceback.format_exc()
    finally:
        tracker.stop()

    data = {"duration_s": None, "energy_kwh": None, "co2eq_g": None, "emissions_kg": None, "country": None}
    try:
        if csv_path.exists():
            with csv_path.open("r", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            if rows:
                last = rows[-1]
                duration   = _ffloat(_pick(last, "duration(s)", "duration"))
                energy_kwh = _ffloat(_pick(last, "power_consumption(kWTh)", "power_consumption(kWh)", "energy_kwh"))
                co2_kg     = _ffloat(_pick(last, "CO2_emissions(kg)", "co2_emissions_kg", "emissions_kg", "emission(kg)"))
                data.update({
                    "duration_s": duration,
                    "energy_kwh": energy_kwh,
                    "emissions_kg": co2_kg,
                    "co2eq_g": co2_kg * 1000.0 if co2_kg is not None else None,
                })
    except Exception:
        pass

    if run_error:
        data["run_error"] = True
        data["stderr"] = err_text.strip()

    payload = json.dumps(data, ensure_ascii=False)
    json_out = os.environ.get("JSON_OUT")
    if json_out:
        try:
            with open(json_out, "w", encoding="utf-8") as f:
                f.write(payload)
        except Exception:
            pass
    print(payload)
    return data

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python eco2ai-api.py <code_file.py>", file=sys.stderr); sys.exit(1)
    p = sys.argv[1]
    if not os.path.exists(p):
        print(json.dumps({"error": f"File not found: {p}"})); sys.exit(2)
    run_and_track_file(p)
