# src/tracarbon-api.py
import os
import sys
import json
import time
import traceback
import runpy

# Tracarbon
# pip install tracarbon
from tracarbon.builder import TracarbonBuilder, TracarbonConfiguration
from tracarbon.exporters import StdoutExporter
from tracarbon.general_metrics import EnergyConsumptionGenerator, CarbonEmissionGenerator

def _as_float(x, default=None):
    try:
        return float(x)
    except Exception:
        return default


def _value_from_metric_obj(obj):
    """
    Les objets du metric_report peuvent être des modèles (attribut .value)
    ou des dicts {'value': ...}. On essaie plusieurs accès.
    """
    if hasattr(obj, "value"):
        return getattr(obj, "value")
    if isinstance(obj, dict):
        if "value" in obj:
            return obj["value"]
        # parfois imbriqué {'value': {'value': x}}
        val = obj.get("value")
        if isinstance(val, dict) and "value" in val:
            return val["value"]
    # dernier recours
    return obj


def run_and_track_file(code_file: str) -> dict:
    # Configuration compacte et silencieuse
    cfg = TracarbonConfiguration(
        metric_prefix_name="green_assistant",
        interval_in_seconds=1,
        log_level="ERROR",
        co2signal_api_key=os.getenv("CO2SIGNAL_API_KEY", "")
    )

    exporter = StdoutExporter(metric_generators=[
        EnergyConsumptionGenerator(),
        CarbonEmissionGenerator(),
    ])

    tc = TracarbonBuilder(configuration=cfg).with_exporter(exporter).build()

    run_error = False
    err_text = ""
    t0 = time.time()

    try:
        tc.start()
        runpy.run_path(code_file, run_name="__main__")
    except SystemExit:
        pass
    except Exception:
        run_error = True
        err_text = traceback.format_exc()
    finally:
        tc.stop()

    duration_s = time.time() - t0

    # Extraction des métriques
    energy_kwh = None
    emissions_kg = None
    co2eq_g = None
    try:
      # tc.report.metric_report: dict avec EnergyConsumption / CarbonEmission
      report = getattr(tc, "report", None)
      metric_report = getattr(report, "metric_report", {}) or {}
      for name, metric in metric_report.items():
          lname = str(name).lower()
          val = _as_float(_value_from_metric_obj(metric))
          if val is None:
              continue
          if "energy" in lname:
              energy_kwh = val  # attendu en kWh
          if "carbon" in lname or "co2" in lname:
              # Selon config, valeur en kg ou g. On fournit les deux champs.
              # Heuristique simple : si val > 1e3 on suppose g.
              if val > 1e3:
                  co2eq_g = val
                  emissions_kg = val / 1000.0
              else:
                  emissions_kg = val
                  co2eq_g = val * 1000.0
    except Exception:
        pass

    data = {
        "duration_s": duration_s,
        "energy_kwh": energy_kwh,
        "co2eq_g": co2eq_g,
        "emissions_kg": emissions_kg,
    }
    if run_error:
        data["run_error"] = True
        data["stderr"] = err_text.strip()

    # Option JSON_OUT (utile pour les benchs)
    json_out = os.getenv("JSON_OUT")
    if json_out:
        try:
            with open(json_out, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except Exception:
            pass

    print(json.dumps(data, ensure_ascii=False))
    return data


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tracarbon-api.py <code_file.py>", file=sys.stderr)
        sys.exit(1)
    script = sys.argv[1]
    if not os.path.exists(script):
        print(json.dumps({"error": f"File not found: {script}"}))
        sys.exit(2)
    run_and_track_file(script)

