// src/extension.ts
import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';
import { execFile } from 'child_process';
import * as os from 'os';
import { promisify } from 'util';

const execFileAsync = promisify(execFile);

/* ===== Types minimaux ===== */
type Lang = 'python' | 'javascript' | 'unknown';
interface AnalyzeMessage { command: 'analyzeCode'; code: string; }
interface CarbonPayload {
  emissions_kg?: number; duration_s?: number | null; energy_kwh?: number | null;
  cpu_energy_kwh?: number | null; gpu_energy_kwh?: number | null; ram_energy_kwh?: number | null;
  cpu_power_w?: number | null; gpu_power_w?: number | null; ram_power_w?: number | null;
  country?: string | null; region?: string | null; cloud_provider?: string | null;
  stderr?: string; returncode?: number; [k: string]: unknown;
}

/* ===== Détection légère ===== */
function detectLanguage(code: string): Lang {
  if (/^\s*import\s+\w+/m.test(code) || /\bdef\s+\w+\s*\(/.test(code)) { return 'python'; }
  if (/\bfunction\s+\w+\s*\(|=>\s*{/.test(code)) { return 'javascript'; }
  return 'unknown';
}

function detectFrameworksPython(code: string): string[] {
  const libs = ['numpy', 'pandas', 'torch', 'tensorflow', 'requests'];
  return libs.filter((lib) => new RegExp(`\\b(?:import|from)\\s+${lib}\\b`).test(code));
}

function detectEnergySmellsPython(code: string): string[] {
  const smells: string[] = [];
  const hasFor = /\bfor\s+[^\n:]+:/m.test(code);

  // sleep près d'une boucle
  if (hasFor && /for[^\n]*:[\s\S]{0,1200}?time\s*\.\s*sleep\s*\(/m.test(code)) {
    smells.push('sleep_dans_boucle');
  }
  // boucles imbriquées
  if (/for[^\n]*:[\s\S]{0,800}?for[^\n]*:/m.test(code)) {
    smells.push('boucles_imbriquees');
  }
  // boucle inutile range(N)
  if (/range\s*\(\s*(10|[2-9]\d|100|1000)\s*\)/m.test(code)) {
    smells.push('boucle_inutile_xN');
  }
  // I/O dans la boucle
  if (hasFor && /for[^\n]*:[\s\S]{0,1000}?\b(open|read|write)\s*\(/m.test(code)) {
    smells.push('IO_dans_boucle');
  }
  // non vectorisé avec numpy
  if (/\b(?:import|from)\s+numpy\b/.test(code) && hasFor && /\+=/.test(code)) {
    smells.push('non_vectorise_avec_numpy');
  }
  return smells;
}

function quickSuggestions(smells: string[], frameworks: string[]): string[] {
  const s: string[] = [];
  if (smells.includes('sleep_dans_boucle')) { s.push('Éviter time.sleep() dans les boucles (scheduler/événements).'); }
  if (smells.includes('boucles_imbriquees')) { s.push('Réduire la profondeur ou vectoriser (NumPy/Pandas).'); }
  if (smells.includes('boucle_inutile_xN')) { s.push('Limiter les répétitions (réduire range(), mémoïsation).'); }
  if (smells.includes('IO_dans_boucle')) { s.push('Regrouper les I/O (lecture/écriture en bloc, bufferisation).'); }
  if (smells.includes('non_vectorise_avec_numpy') || frameworks.includes('pandas')) {
    s.push('Vectoriser avec NumPy/Pandas (broadcasting, groupby, agg).');
  }
  return s;
}

/* ===== Utils ===== */
function fmtNum(v: unknown, f?: (n: number) => string): string {
  if (v === undefined || v === null || v === '') { return '—'; }
  if (typeof v === 'number' && isFinite(v)) { return f ? f(v) : String(v); }
  return String(v);
}

function pickPythonCmd(root?: string): string {
  const isWin = process.platform === 'win32';
  const venvs = root ? [
    path.join(root, '.venv', isWin ? 'Scripts\\python.exe' : 'bin/python'),
    path.join(root, 'venv',  isWin ? 'Scripts\\python.exe' : 'bin/python')
  ] : [];
  const fallbacks = [isWin ? 'py' : 'python3', 'python'];
  for (const p of [...venvs, ...fallbacks]) {
    if (p === 'py' || p === 'python3' || p === 'python') { return p; }
    if (fs.existsSync(p)) { return p; }
  }
  return 'python';
}

async function runCarbon(apiPath: string, code: string): Promise<string> {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'green_code_'));
  const codeFile = path.join(tmp, 'snippet.py');
  fs.writeFileSync(codeFile, code, 'utf8');
  const py = pickPythonCmd(vscode.workspace.workspaceFolders?.[0]?.uri.fsPath);

  try {
    const { stdout, stderr } = await execFileAsync(py, [apiPath, codeFile], {
      shell: process.platform === 'win32' && py === 'py'
    });
    const out = (stdout ?? '').toString().trim();
    const err = (stderr ?? '').toString().trim();

    let payload: CarbonPayload | null = null;
    let kg = Number.NaN;
    try {
      payload = JSON.parse(out) as CarbonPayload;
      if (typeof payload.emissions_kg === 'number') { kg = payload.emissions_kg; }
    } catch {
      const f = parseFloat(out);
      if (isFinite(f)) { kg = f; }
      payload = {};
    }

    const headline = !Number.isNaN(kg)
      ? (kg > 0 && kg < 1e-5 ? `${kg.toExponential(2)} kgCO₂` : `${kg.toFixed(5)} kgCO₂`)
      : (err ? `Erreur : ${err}` : 'Empreinte : indisponible');

    return buildAnalysisBlock(code, payload, headline);
  } finally {
    try { fs.rmSync(tmp, { recursive: true, force: true }); } catch { /* noop */ }
  }
}

/* ===== Bloc d’analyse ===== */
function buildAnalysisBlock(code: string, m: CarbonPayload | null, headline: string): string {
  const lang = detectLanguage(code);
  const frameworks = lang === 'python' ? detectFrameworksPython(code) : [];
  const smells = lang === 'python' ? detectEnergySmellsPython(code) : [];
  const recos = quickSuggestions(smells, frameworks);

  const lines: string[] = [
    `Langage : ${lang}`,
    `Frameworks : ${frameworks.join(', ') || '—'}`,
    `Empreinte carbone estimée : ${headline}`
  ];

  if (m) {
    const duration = fmtNum(m.duration_s);
    const energy   = fmtNum(m.energy_kwh, (v) => `${v.toExponential(3)} kWh`);
    const cpuE     = fmtNum(m.cpu_energy_kwh, (v) => `${v.toExponential(3)} kWh`);
    const gpuE     = fmtNum(m.gpu_energy_kwh, (v) => `${v.toExponential(3)} kWh`);
    const ramE     = fmtNum(m.ram_energy_kwh, (v) => `${v.toExponential(3)} kWh`);
    const cpuP     = fmtNum(m.cpu_power_w, (v) => `${v.toFixed(2)} W`);
    const gpuP     = fmtNum(m.gpu_power_w, (v) => `${v.toFixed(2)} W`);
    const ramP     = fmtNum(m.ram_power_w, (v) => `${v.toFixed(2)} W`);
    const country  = fmtNum(m.country);
    const region   = fmtNum(m.region);
    const cloud    = fmtNum(m.cloud_provider);

    if (duration !== '—') { lines.push(`Durée : ${duration} s`); }
    if (energy   !== '—') { lines.push(`Énergie totale : ${energy}`); }
    if (cpuE !== '—' || cpuP !== '—') { lines.push(`CPU : ${cpuE} / ${cpuP}`); }
    if (gpuE !== '—' || gpuP !== '—') { lines.push(`GPU : ${gpuE} / ${gpuP}`); }
    if (ramE !== '—' || ramP !== '—') { lines.push(`RAM : ${ramE} / ${ramP}`); }
    if (country !== '—' || region !== '—' || cloud !== '—') {
      lines.push(`Pays : ${country} | Région : ${region} | Cloud : ${cloud}`);
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
export function activate(context: vscode.ExtensionContext): void {
  const provider = new GreenSoftwareView(context.extensionUri);
  context.subscriptions.push(vscode.window.registerWebviewViewProvider(GreenSoftwareView.viewType, provider));
}
export function deactivate(): void { /* noop */ }

/* ===== Webview (bouton centré en bas) ===== */
class GreenSoftwareView implements vscode.WebviewViewProvider {
  public static readonly viewType = 'greenSoftware.greenSoftwareView';
  private _view?: vscode.WebviewView;
  private _subs: vscode.Disposable[] = [];

  constructor(private readonly _uri: vscode.Uri) {}

  public resolveWebviewView(webviewView: vscode.WebviewView): void {
    this._view = webviewView;
    webviewView.webview.options = { enableScripts: true, localResourceRoots: [this._uri] };
    webviewView.webview.html = this._html();

    const sub = webviewView.webview.onDidReceiveMessage(async (msg: AnalyzeMessage) => {
      if (!msg || msg.command !== 'analyzeCode') { return; }
      const code = String(msg.code ?? '');
      if (!code.trim()) {
        webviewView.webview.postMessage({ command: 'analysisResult', result: 'Veuillez coller un code à analyser.' });
        return;
      }
      try {
        const api = vscode.Uri.joinPath(this._uri, 'src', 'codecarbon-api.py').fsPath;
        const result = await runCarbon(api, code);
        webviewView.webview.postMessage({ command: 'analysisResult', result });
      } catch (e: unknown) {
        const m = e instanceof Error ? e.message : String(e);
        webviewView.webview.postMessage({ command: 'analysisResult', result: `Analyse indisponible : ${m}` });
      }
    });
    this._subs.push(sub);
    webviewView.onDidDispose(() => { this.dispose(); });
  }

  public dispose(): void {
    while (this._subs.length > 0) {
      const d = this._subs.pop();
      try {
        if (d) { d.dispose(); }
      } catch {
        /* noop */
      }
    }
  }

  private _html(): string {
    const style = `
      <style>
        body { font-family: sans-serif; padding: 12px; }
        textarea { width: 100%; height: 170px; font-family: monospace; font-size: 14px; }
        button { margin-top: 10px; padding: 6px 16px; background-color: #275a29ff; color: white; border: none; cursor: pointer; border-radius: 6px; }
        pre { background: #0e0e0e; color: #d9fdd3; padding: 12px; border-radius: 8px; white-space: pre-wrap; }
      </style>
    `;
    const script = `
      <script>
        const vscode = acquireVsCodeApi();
        function analyze() {
          const t = document.getElementById('codeInput');
          const b = document.getElementById('btn');
          b.disabled = true;
          vscode.postMessage({ command: 'analyzeCode', code: t.value });
        }
        window.addEventListener('message', e => {
          const m = e.data;
          if (m.command === 'analysisResult') {
            document.getElementById('result').innerHTML = '<pre>' + m.result + '</pre>';
            document.getElementById('btn').disabled = false;
          }
        });
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


