# src/carbontracker-api.py
import sys, os, json, tempfile, traceback, runpy, time, logging, warnings
from pathlib import Path

logging.basicConfig(level=logging.CRITICAL)
logging.getLogger("carbontracker").setLevel(logging.CRITICAL)
warnings.filterwarnings("ignore")

from carbontracker.tracker import CarbonTracker
from carbontracker import parser as ct_parser


def _dump_and_print(data: dict) -> dict:
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


def run_and_track_file(code_file: str) -> dict:
    data = {"duration_s": None, "energy_kwh": None, "co2eq_g": None, "emissions_kg": None}
    run_error, err_text = False, ""

    # 1) exécution + logs dans un répertoire temporaire
    log_dir = Path(tempfile.mkdtemp(prefix="ct_logs_"))

    try:
        # Cycle explicite = plus prévisible sur Windows
        tracker = CarbonTracker(
            epochs=1, monitor_epochs=1, epochs_before_pred=1,
            update_interval=1, verbose=0, log_dir=str(log_dir),
            components="cpu",
        )
        tracker.epoch_start()
        try:
            runpy.run_path(code_file, run_name="__main__")
        finally:
            tracker.epoch_end()
            tracker.stop()
    except SystemExit:
        pass
    except Exception:
        run_error = True
        err_text = traceback.format_exc()

    # petit délai pour laisser le temps au flush
    time.sleep(0.15)

    # 2) parsing des logs — avec Fallbacks
    try:
        logs = ct_parser.parse_all_logs(log_dir=str(log_dir)) or []

        # Fallback 1: certains CarbonTracker écrivent dans un sous-dossier
        if not logs and (log_dir / "carbontracker").exists():
            logs = ct_parser.parse_all_logs(log_dir=str(log_dir / "carbontracker"))

        # Fallback 2: dossier par défaut (~/.carbontracker/logs)
        if not logs:
            home_default = Path.home() / ".carbontracker" / "logs"
            if home_default.exists():
                logs = ct_parser.parse_all_logs(log_dir=str(home_default))

        if logs:
            last = logs[-1]
            actual = (last or {}).get("actual") or {}
            dur = actual.get("duration (s)")
            energy = actual.get("energy (kWh)")
            co2g = actual.get("co2eq (g)")
            data["duration_s"]  = float(dur) if dur is not None else None
            data["energy_kwh"]  = float(energy) if energy is not None else None
            data["co2eq_g"]     = float(co2g) if co2g is not None else None
            data["emissions_kg"] = (data["co2eq_g"]/1000.0) if data["co2eq_g"] is not None else None
    except Exception:
        # on laisse les valeurs à None si parsing impossible
        pass

    if run_error:
        data["run_error"] = True
        data["stderr"] = err_text.strip()

    return _dump_and_print(data)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python carbontracker-api.py <code_file.py>", file=sys.stderr)
        sys.exit(1)
    p = sys.argv[1]
    if not os.path.exists(p):
        print(json.dumps({"error": f"File not found: {p}"}))
        sys.exit(2)
    run_and_track_file(p)
