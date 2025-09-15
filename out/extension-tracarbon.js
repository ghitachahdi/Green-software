"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.activate = activate;
exports.deactivate = deactivate;
const vscode = __importStar(require("vscode"));
const path = __importStar(require("path"));
const fs = __importStar(require("fs"));
const child_process_1 = require("child_process");
const os = __importStar(require("os"));
/* ===== Détection & recommandations (compact) ===== */
function detectLanguage(code) {
    if (/^\s*import\s+\w+/m.test(code) || /\bdef\s+\w+\s*\(/.test(code)) {
        return "python";
    }
    if (/\bfunction\s+\w+\s*\(|=>\s*{/.test(code)) {
        return "javascript";
    }
    return "unknown";
}
function detectFrameworksPython(code) {
    const libs = ["numpy", "pandas", "torch", "tensorflow", "requests", "multiprocessing"];
    return libs.filter((lib) => new RegExp(`\\b(?:import|from)\\s+${lib}\\b`).test(code));
}
function hasSleepInLoop(code) {
    const re = /(^[ \t]*for\s+\w+\s+in\s+range\s*\([^)]*\):)([\s\S]*?)(?=^[^\s]|$)/gm;
    let m;
    while ((m = re.exec(code)) !== null) {
        const block = m[2];
        if (/\n[ \t]+time\.sleep\s*\(/.test(block)) {
            return true;
        }
    }
    return false;
}
function detectEnergySmellsPython(code) {
    const smells = [];
    if (hasSleepInLoop(code)) {
        smells.push("sleep_dans_boucle");
    }
    if (/for\s+\w+\s+in\s+range\s*\([^)]*\):[\s\S]*?(?:open\(|read\(|write\()/.test(code)) {
        smells.push("IO_dans_boucle");
    }
    if (/for\s+\w+\s+in\s+range\s*\([^)]*\):[\s\S]*?\w+\s*\+=\s*["']/.test(code)) {
        smells.push("concat_string_dans_boucle");
    }
    if (/for[\s\S]*?for[\s\S]*?for/.test(code) || /for[\s\S]*?for/.test(code)) {
        smells.push("boucles_imbriquees");
    }
    if (/\b(?:import|from)\s+numpy\b/.test(code) && /for\s+.*:\s*[\s\S]*\+=/.test(code)) {
        smells.push("non_vectorise_alors_numpy_dispo");
    }
    if (/requests\.(?:get|post|put|delete|patch|head)\(/.test(code) && /for\s+/.test(code)) {
        smells.push("requetes_repetitives_sequentielles");
    }
    return smells;
}
function suggestionsFor(smells, frameworks) {
    const sug = [];
    if (smells.includes("non_vectorise_alors_numpy_dispo")) {
        sug.push("Vectoriser avec NumPy (np.dot, np.sum, broadcasting).");
    }
    if (smells.includes("sleep_dans_boucle")) {
        sug.push("Éviter time.sleep() dans les boucles; utiliser un scheduler/événements.");
    }
    if (smells.includes("IO_dans_boucle")) {
        sug.push("Regrouper les I/O hors boucle (bufferisation, lecture/écriture en bloc).");
    }
    if (smells.includes("concat_string_dans_boucle")) {
        sug.push("Utiliser ''.join() ou io.StringIO plutôt que s += ... en boucle.");
    }
    if (smells.includes("requetes_repetitives_sequentielles")) {
        sug.push("Mutualiser (requests.Session) et paralléliser (asyncio/threading) avec throttle.");
    }
    if (frameworks.includes("pandas")) {
        sug.push("Préférer les opérations Pandas vectorisées à apply/itertuples.");
    }
    return sug;
}
/* ====== Résolution Python fiable + préflight tracarbon ====== */
function getVsCodePythonSetting() {
    const cfg = vscode.workspace.getConfiguration("python");
    const v1 = cfg.get("defaultInterpreterPath");
    if (v1 && fs.existsSync(v1)) {
        return v1;
    }
    const v0 = cfg.get("pythonPath");
    if (v0 && fs.existsSync(v0)) {
        return v0;
    }
    return undefined;
}
function resolvePython() {
    const ws = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || "";
    const fromSetting = getVsCodePythonSetting();
    if (fromSetting) {
        return { cmd: fromSetting, args: [], note: "vscodeSetting" };
    }
    const venvs = [
        path.join(ws, ".venv", "Scripts", "python.exe"),
        path.join(ws, "venv", "Scripts", "python.exe"),
        path.join(ws, ".venv", "bin", "python"),
        path.join(ws, "venv", "bin", "python"),
    ].filter((p) => fs.existsSync(p));
    if (venvs.length > 0) {
        return { cmd: venvs[0], args: [], note: "venv" };
    }
    if (process.platform === "win32") {
        return { cmd: "py", args: ["-3"], note: "pyLauncher" };
    }
    return { cmd: "python3", args: [], note: "python3Fallback" };
}
function preflightTracarbon(py) {
    return new Promise((resolve) => {
        const args = [...py.args, "-c", 'import importlib,sys; importlib.import_module("tracarbon"); print("OK")'];
        (0, child_process_1.execFile)(py.cmd, args, { timeout: 15000 }, (err, stdout, stderr) => {
            if (err) {
                resolve({ ok: false, msg: (stderr || stdout || String(err)).toString() });
                return;
            }
            resolve({ ok: /OK/.test(String(stdout)) });
        });
    });
}
/* ============================ Activation ============================ */
function activate(context) {
    const provider = new TracarbonView(context.extensionUri);
    context.subscriptions.push(vscode.window.registerWebviewViewProvider(TracarbonView.viewType, provider));
}
function deactivate() { }
class TracarbonView {
    _extensionUri;
    static viewType = "greenSoftware.tracarbonView";
    _view;
    constructor(_extensionUri) {
        this._extensionUri = _extensionUri;
    }
    resolveWebviewView(webviewView) {
        this._view = webviewView;
        webviewView.webview.options = { enableScripts: true, localResourceRoots: [this._extensionUri] };
        webviewView.webview.html = this._getHtml();
        webviewView.webview.onDidReceiveMessage(async (message) => {
            try {
                if (!message || message.command !== "analyzeCode") {
                    return;
                }
                const code = String(message.code ?? "");
                const tempFilePath = path.join(os.tmpdir(), "tracarbon_tmp_code.py");
                fs.writeFileSync(tempFilePath, code, "utf8");
                const py = resolvePython();
                const interpInfo = `${py.cmd} ${py.args.join(" ")}`.trim();
                // Vérifier la présence de tracarbon dans CET interpréteur
                const check = await preflightTracarbon(py);
                if (!check.ok) {
                    const pipCmd = (py.cmd === "py")
                        ? "py -3 -m pip install tracarbon"
                        : `"${py.cmd}" -m pip install tracarbon`;
                    const tip = [
                        "Tracarbon n’est pas installé dans l’interpréteur courant.",
                        `Interpréteur : ${interpInfo || "(inconnu)"}`,
                        "Installe-le :",
                        `  ${pipCmd}`,
                        'Puis, si besoin, sélectionnez la venv via "Python: Select Interpreter".'
                    ].join("\n");
                    const analysisBlock = "Analyse de l’empreinte carbone du code\n" +
                        "-------------------------------------\n" +
                        "Empreinte carbone estimée : Erreur\n" +
                        `Notes :\n${tip}`;
                    webviewView.webview.postMessage({ command: "analysisResult", code, result: analysisBlock });
                    return;
                }
                // Appel du wrapper tracarbon
                const apiPath = path.join(this._extensionUri.fsPath, "src", "tracarbon-api.py");
                const args = [...py.args, apiPath, tempFilePath];
                (0, child_process_1.execFile)(py.cmd, args, { timeout: 120000 }, (_error, stdout, stderr) => {
                    let headline = "Empreinte : indisponible";
                    const out = String(stdout || "").trim();
                    const err = String(stderr || "").trim();
                    // Parse JSON du wrapper
                    let m = {};
                    let kg = Number.NaN;
                    try {
                        const parsed = JSON.parse(out);
                        m = parsed;
                        const v = parsed["emissions_kg"];
                        if (typeof v === "number") {
                            kg = v;
                        }
                    }
                    catch {
                        const n = parseFloat(out);
                        if (!Number.isNaN(n)) {
                            kg = n;
                        }
                    }
                    const lang = detectLanguage(code);
                    const frameworks = lang === "python" ? detectFrameworksPython(code) : [];
                    const smells = lang === "python" ? detectEnergySmellsPython(code) : [];
                    const recos = suggestionsFor(smells, frameworks);
                    if (!Number.isNaN(kg)) {
                        headline = kg > 0 && kg < 1e-5 ? `${kg.toExponential(2)} kgCO₂` : `${kg.toFixed(5)} kgCO₂`;
                    }
                    else {
                        headline = err ? `Erreur : ${err}` : "Erreur lors de l’analyse";
                    }
                    const fmt = (x, f) => {
                        if (x === undefined || x === null || x === "") {
                            return "—";
                        }
                        if (typeof x === "number" && f) {
                            return f(x);
                        }
                        return String(x);
                    };
                    const lines = [];
                    lines.push(`Langage : ${lang}`);
                    lines.push(`Frameworks : ${frameworks.join(", ") || "—"}`);
                    lines.push(`Interpréteur : ${interpInfo}`);
                    lines.push(`Empreinte carbone estimée : ${headline}`);
                    const duration = fmt(m["duration_s"]);
                    const energy = fmt(m["energy_kwh"], (v) => `${v.toExponential(3)} kWh`);
                    const co2g = fmt(m["co2eq_g"], (v) => `${v.toFixed(3)} g`);
                    if (duration !== "—") {
                        lines.push(`Durée : ${duration} s`);
                    }
                    if (energy !== "—") {
                        lines.push(`Énergie totale : ${energy}`);
                    }
                    if (co2g !== "—") {
                        lines.push(`CO₂eq total : ${co2g}`);
                    }
                    const smellsLine = smells.length ? smells.join(", ") : "—";
                    lines.push(`Motifs énergivores détectés : ${smellsLine}`);
                    const recosBlock = recos.length ? recos.map((r) => `• ${r}`).join("\n") : "• Aucune recommandation détectée.";
                    const notes = [];
                    if (err) {
                        notes.push(err);
                    }
                    const stderrFromJson = typeof m["stderr"] === "string" ? m["stderr"] : "";
                    if (stderrFromJson) {
                        notes.push(stderrFromJson);
                    }
                    if (notes.length > 0) {
                        lines.push(`Notes :\n${notes.join("\n")}`);
                    }
                    const analysisBlock = "Analyse de l’empreinte carbone du code\n" +
                        "-------------------------------------\n" +
                        lines.join("\n") +
                        "\nRecommandations :\n" +
                        recosBlock;
                    webviewView.webview.postMessage({ command: "analysisResult", code, result: analysisBlock });
                });
            }
            catch {
                const code = String(message?.code ?? "");
                webviewView.webview.postMessage({
                    command: "analysisResult",
                    code,
                    result: "Analyse indisponible (erreur inattendue).",
                });
            }
        });
    }
    _getHtml() {
        const style = `
      <style>
        :root { color-scheme: dark light; }
        body { font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; padding: 12px; }
        h2 { margin: 0 0 8px; }
        .editor { width: 100%; height: 170px; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 14px; }
        .bar { display: flex; justify-content: center; margin: 8px 0 12px; }
        button { padding: 8px 18px; background: #2f7d32; color: #fff; border: 0; border-radius: 8px; cursor: pointer; }
        pre { background: #111; color: #d9fdd3; padding: 12px; border-radius: 8px; white-space: pre-wrap; }
      </style>
    `;
        const script = `
      <script>
        const vscode = acquireVsCodeApi();
        function sendCode() {
          const code = (document.getElementById('codeInput') as HTMLTextAreaElement).value;
          vscode.postMessage({ command: 'analyzeCode', code });
        }
        window.addEventListener('message', ev => {
          const msg = ev.data;
          if (msg.command === 'analysisResult') {
            (document.getElementById('result') as HTMLDivElement).innerHTML = '<pre>' + msg.result + '</pre>';
          }
        });
      </script>
    `;
        return `
      <!doctype html>
      <html lang="fr">
        <head>
          <meta charset="UTF-8" />
          <meta name="viewport" content="width=device-width, initial-scale=1.0" />
          <title>Green Assistant • Tracarbon</title>
          ${style}
        </head>
        <body>
          <h2>Green Assistant 🌱</h2>
          <textarea id="codeInput" class="editor" placeholder="Collez ici votre code Python à analyser..."></textarea>
          <div class="bar"><button onclick="sendCode()">Analyser</button></div>
          <div id="result"></div>
          ${script}
        </body>
      </html>
    `;
    }
}
//# sourceMappingURL=extension-tracarbon.js.map