import sys, os, csv, json, tempfile, subprocess, logging, warnings
from pathlib import Path
from codecarbon import EmissionsTracker

# calmer les logs
logging.basicConfig(level=logging.CRITICAL)
logging.getLogger("codecarbon").setLevel(logging.CRITICAL)
warnings.filterwarnings("ignore")
os.environ.setdefault("CODECARBON_LOG_LEVEL", "error")

def _ffloat(x, default=None):
    try:
        return float(x) if x not in (None, "", "None") else default
    except Exception:
        return default
def measure_file(file_path: str) -> dict:
    out_dir = Path(tempfile.mkdtemp(prefix="cc_run_"))
    tracker = EmissionsTracker(
        output_dir=str(out_dir),
        output_file="emissions.csv",
        measure_power_secs=1,
        save_to_file=True,
        log_level="error",
    )

    run_stderr, returncode = "", 0
    tracker.start()
    try:
        p = subprocess.run([sys.executable, file_path], capture_output=True, text=True, timeout=120)
        returncode = p.returncode
        run_stderr = (p.stderr or "").strip()
    finally:
        emissions_kg_stop = tracker.stop() or 0.0

    data = {
        "emissions_kg": float(emissions_kg_stop) if emissions_kg_stop is not None else None,
        "stderr": run_stderr if returncode != 0 else "",
        "returncode": returncode,
        "duration_s": None,
        "energy_kwh": None,
        "cpu_energy_kwh": None, "gpu_energy_kwh": None, "ram_energy_kwh": None,
        "cpu_power_w": None, "gpu_power_w": None, "ram_power_w": None,
        "country_name": None, "country_iso_code": None, "region": None, "cloud_provider": None,
    }

    # parse emissions.csv
    try:
        csv_path = out_dir / "emissions.csv"
        if csv_path.exists():
            with csv_path.open("r", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            if rows:
                last = rows[-1]
                data["duration_s"]       = _ffloat(last.get("duration"))
                data["energy_kwh"]       = _ffloat(last.get("energy_consumed"))
                data["cpu_energy_kwh"]   = _ffloat(last.get("cpu_energy"))
                data["gpu_energy_kwh"]   = _ffloat(last.get("gpu_energy"))
                data["ram_energy_kwh"]   = _ffloat(last.get("ram_energy"))
                data["cpu_power_w"]      = _ffloat(last.get("cpu_power"))
                data["gpu_power_w"]      = _ffloat(last.get("gpu_power"))
                data["ram_power_w"]      = _ffloat(last.get("ram_power"))
                csv_emis = _ffloat(last.get("emissions"))
                if csv_emis is not None:
                    data["emissions_kg"] = csv_emis
    except Exception:
        pass

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
        print("Usage: python codecarbon-api.py <code_file.py>", file=sys.stderr); sys.exit(1)
    measure_file(sys.argv[1])
