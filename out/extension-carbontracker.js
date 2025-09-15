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
// src/extension2.ts
const vscode = __importStar(require("vscode"));
const path = __importStar(require("path"));
const fs = __importStar(require("fs"));
const child_process_1 = require("child_process");
const os = __importStar(require("os"));
const util_1 = require("util");
const execFileAsync = (0, util_1.promisify)(child_process_1.execFile);
/* ===== Détection légère ===== */
function detectLanguage(code) {
    if (/^\s*import\s+\w+/m.test(code) || /\bdef\s+\w+\s*\(/.test(code)) {
        return 'python';
    }
    if (/\bfunction\s+\w+\s*\(|=>\s*{/.test(code)) {
        return 'javascript';
    }
    return 'unknown';
}
function detectFrameworksPython(code) {
    const libs = ['numpy', 'pandas', 'torch', 'tensorflow', 'requests'];
    return libs.filter((lib) => new RegExp(`\\b(?:import|from)\\s+${lib}\\b`).test(code));
}
function detectEnergySmellsPython(code) {
    const smells = [];
    const hasFor = /\bfor\s+[^\n:]+:/m.test(code);
    if (hasFor && /for[^\n]*:[\s\S]{0,1200}?time\s*\.\s*sleep\s*\(/m.test(code)) {
        smells.push('sleep_dans_boucle');
    }
    if (/for[^\n]*:[\s\S]{0,800}?for[^\n]*:/m.test(code)) {
        smells.push('boucles_imbriquees');
    }
    if (/range\s*\(\s*(10|[2-9]\d|100|1000)\s*\)/m.test(code)) {
        smells.push('boucle_inutile_xN');
    }
    if (hasFor && /for[^\n]*:[\s\S]{0,1000}?\b(open|read|write)\s*\(/m.test(code)) {
        smells.push('IO_dans_boucle');
    }
    if (/\b(?:import|from)\s+numpy\b/.test(code) && hasFor && /\+=/.test(code)) {
        smells.push('non_vectorise_avec_numpy');
    }
    return smells;
}
function quickSuggestions(smells, frameworks) {
    const s = [];
    if (smells.includes('sleep_dans_boucle')) {
        s.push('Éviter time.sleep() dans les boucles (scheduler/événements).');
    }
    if (smells.includes('boucles_imbriquees')) {
        s.push('Réduire la profondeur ou vectoriser (NumPy/Pandas).');
    }
    if (smells.includes('boucle_inutile_xN')) {
        s.push('Limiter les répétitions (réduire range(), mémoïsation).');
    }
    if (smells.includes('IO_dans_boucle')) {
        s.push('Regrouper les I/O (lecture/écriture en bloc, bufferisation).');
    }
    if (smells.includes('non_vectorise_avec_numpy') || frameworks.includes('pandas')) {
        s.push('Vectoriser avec NumPy/Pandas (broadcasting, groupby, agg).');
    }
    return s;
}
/* ===== Utils ===== */
function fmtNum(v, f) {
    if (v === undefined || v === null || v === '') {
        return '—';
    }
    if (typeof v === 'number' && isFinite(v)) {
        return f ? f(v) : String(v);
    }
    return String(v);
}
function pickPythonCmd(root) {
    const isWin = process.platform === 'win32';
    const venvs = root ? [
        path.join(root, '.venv', isWin ? 'Scripts\\python.exe' : 'bin/python'),
        path.join(root, 'venv', isWin ? 'Scripts\\python.exe' : 'bin/python')
    ] : [];
    const fallbacks = [isWin ? 'py' : 'python3', 'python'];
    for (const p of [...venvs, ...fallbacks]) {
        if (p === 'py' || p === 'python3' || p === 'python') {
            return p;
        }
        if (fs.existsSync(p)) {
            return p;
        }
    }
    return 'python';
}
/* ===== Intégration CarbonTracker (via carbontracker-api.py) ===== */
async function runCarbonTracker(apiPath, code) {
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'green_code_'));
    const codeFile = path.join(tmpDir, 'snippet.py');
    fs.writeFileSync(codeFile, code, 'utf8');
    const py = pickPythonCmd(vscode.workspace.workspaceFolders?.[0]?.uri.fsPath);
    try {
        const { stdout, stderr } = await execFileAsync(py, [apiPath, codeFile], {
            shell: process.platform === 'win32' && py === 'py'
        });
        const out = (stdout ?? '').toString().trim();
        const err = (stderr ?? '').toString().trim();
        let payload = null;
        let kg = Number.NaN;
        try {
            payload = JSON.parse(out);
            if (typeof payload.emissions_kg === 'number') {
                kg = payload.emissions_kg;
            }
        }
        catch {
            const f = parseFloat(out);
            if (isFinite(f)) {
                kg = f;
            }
            payload = {};
        }
        const headline = !Number.isNaN(kg)
            ? (kg > 0 && kg < 1e-5 ? `${kg.toExponential(2)} kgCO₂` : `${kg.toFixed(5)} kgCO₂`)
            : (err ? `Erreur : ${err}` : 'Empreinte : indisponible');
        return buildAnalysisBlock(code, payload, headline);
    }
    finally {
        try {
            fs.rmSync(tmpDir, { recursive: true, force: true });
        }
        catch { /* noop */ }
    }
}
/* ===== Construction du rapport ===== */
function buildAnalysisBlock(code, m, headline) {
    const lang = detectLanguage(code);
    const frameworks = lang === 'python' ? detectFrameworksPython(code) : [];
    const smells = lang === 'python' ? detectEnergySmellsPython(code) : [];
    const recos = quickSuggestions(smells, frameworks);
    const lines = [
        `Langage : ${lang}`,
        `Frameworks : ${frameworks.join(', ') || '—'}`,
        `Empreinte carbone estimée : ${headline}`
    ];
    if (m) {
        const duration = fmtNum(m.duration_s);
        const energy = fmtNum(m.energy_kwh, (v) => `${v.toExponential(3)} kWh`);
        const co2g = fmtNum(m.co2eq_g, (v) => `${v.toFixed(3)} g`);
        const country = fmtNum(m.country);
        const region = fmtNum(m.region);
        if (duration !== '—') {
            lines.push(`Durée : ${duration} s`);
        }
        if (energy !== '—') {
            lines.push(`Énergie totale : ${energy}`);
        }
        if (co2g !== '—') {
            lines.push(`CO₂eq total : ${co2g}`);
        }
        if (country !== '—' || region !== '—') {
            lines.push(`Pays/Région : ${country}${region !== '—' ? ` | ${region}` : ''}`);
        }
    }
    lines.push(`Motifs énergivores détectés : ${smells.length ? smells.join(', ') : '—'}`);
    const recosBlock = recos.length ? recos.map((r) => `• ${r}`).join('\n') : '• Aucune recommandation détectée.';
    return [
        'Analyse de l’empreinte carbone du code',
        '-------------------------------------',
        ...lines,
        'Recommandations :',
        recosBlock
    ].join('\n');
}
/* ===== Cycle de vie ===== */
function activate(context) {
    const provider = new GreenSoftwareView(context.extensionUri);
    context.subscriptions.push(vscode.window.registerWebviewViewProvider(GreenSoftwareView.viewType, provider));
}
function deactivate() { }
/* ===== Webview (bouton centré en bas) ===== */
class GreenSoftwareView {
    _uri;
    static viewType = 'greenSoftware.greenSoftwareView';
    _view;
    _subs = [];
    constructor(_uri) {
        this._uri = _uri;
    }
    resolveWebviewView(webviewView) {
        this._view = webviewView;
        webviewView.webview.options = { enableScripts: true, localResourceRoots: [this._uri] };
        webviewView.webview.html = this._html();
        const sub = webviewView.webview.onDidReceiveMessage(async (msg) => {
            if (!msg || msg.command !== 'analyzeCode') {
                return;
            }
            const code = String(msg.code ?? '');
            if (!code.trim()) {
                webviewView.webview.postMessage({ command: 'analysisResult', result: 'Veuillez coller un code à analyser.' });
                return;
            }
            try {
                const api = vscode.Uri.joinPath(this._uri, 'src', 'carbontracker-api.py').fsPath;
                const result = await runCarbonTracker(api, code);
                webviewView.webview.postMessage({ command: 'analysisResult', result });
            }
            catch (e) {
                const m = e instanceof Error ? e.message : String(e);
                webviewView.webview.postMessage({ command: 'analysisResult', result: `Analyse indisponible : ${m}` });
            }
        });
        this._subs.push(sub);
        webviewView.onDidDispose(() => { this.dispose(); });
    }
    dispose() {
        while (this._subs.length) {
            const d = this._subs.pop();
            try {
                if (d) {
                    d.dispose();
                }
            }
            catch { /* noop */ }
        }
    }
    _html() {
        const style = `
      <style>
        html, body { height:100%; }
        body { font-family:sans-serif; padding:12px; display:flex; flex-direction:column; min-height:100%; }
        h2 { margin:0 0 8px 0; }
        textarea{ flex:1; width:100%; box-sizing:border-box; font-family:ui-monospace,Menlo,Consolas,monospace; font-size:13px; border-radius:6px; padding:8px; }
        .bottom{ display:flex; justify-content:center; margin-top:12px; }
        button{ padding:8px 20px; background:#2e7d32; color:#fff; border:none; border-radius:6px; cursor:pointer; }
        button:disabled{ opacity:.6; cursor:not-allowed; }
        pre{ background:#0e0e0e; color:#d9fdd3; padding:12px; border-radius:8px; white-space:pre-wrap; margin-top:12px; }
      </style>`;
        const script = `
      <script>
        const vscode = acquireVsCodeApi();
        function analyze(){ const t=document.getElementById('codeInput'); const b=document.getElementById('btn'); b.disabled=true; vscode.postMessage({command:'analyzeCode', code:t.value}); }
        window.addEventListener('message', e => { const m=e.data; if (m.command==='analysisResult'){ document.getElementById('result').innerHTML='<pre>'+m.result+'</pre>'; document.getElementById('btn').disabled=false; }});
      </script>`;
        return `
      <!doctype html><html lang="fr"><head><meta charset="UTF-8"/><meta name="viewport" content="width=device-width, initial-scale=1.0"/>
      <title>Green Assistant</title>${style}</head>
      <body>
        <h2>Green Assistant 🌱</h2>
        <textarea id="codeInput" placeholder="Collez ici votre code Python à analyser..."></textarea>
        <div class="bottom"><button id="btn" onclick="analyze()">Analyser</button></div>
        <div id="result"></div>
        ${script}
      </body></html>`;
    }
}
//# sourceMappingURL=extension-carbontracker.js.map