// src/extension3.ts
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
interface Eco2Payload {
  emissions_kg?: number; duration_s?: number | null; energy_kwh?: number | null; co2eq_g?: number | null;
  country?: string | null; stderr?: string; [k: string]: unknown;
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
  if (hasFor && /for[^\n]*:[\s\S]{0,1200}?time\s*\.\s*sleep\s*\(/m.test(code)) { smells.push('sleep_dans_boucle'); }
  if (/for[^\n]*:[\s\S]{0,800}?for[^\n]*:/m.test(code)) { smells.push('boucles_imbriquees'); }
  if (/range\s*\(\s*(10|[2-9]\d|100|1000)\s*\)/m.test(code)) { smells.push('boucle_inutile_xN'); }
  if (hasFor && /for[^\n]*:[\s\S]{0,1000}?\b(open|read|write)\s*\(/m.test(code)) { smells.push('IO_dans_boucle'); }
  if (/\b(?:import|from)\s+numpy\b/.test(code) && hasFor && /\+=/.test(code)) { smells.push('non_vectorise_avec_numpy'); }
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
function getVsCodePythonSetting(): string | undefined {
  const cfg = vscode.workspace.getConfiguration('python');
  const v1 = cfg.get<string>('defaultInterpreterPath');
  if (v1 && fs.existsSync(v1)) { return v1; }
  const v0 = cfg.get<string>('pythonPath');
  if (v0 && fs.existsSync(v0)) { return v0; }
  return undefined;
}
function resolvePython(): { cmd: string; args: string[]; label: string } {
  const ws = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '';
  const fromSetting = getVsCodePythonSetting();
  if (fromSetting) { return { cmd: fromSetting, args: [], label: 'vscodeSetting' }; }
  const venvs = [
    path.join(ws, '.venv', 'Scripts', 'python.exe'),
    path.join(ws, 'venv', 'Scripts', 'python.exe'),
    path.join(ws, '.venv', 'bin', 'python'),
    path.join(ws, 'venv', 'bin', 'python'),
  ].filter(p => fs.existsSync(p));
  if (venvs.length) { return { cmd: venvs[0], args: [], label: 'venv' }; }
  if (process.platform === 'win32') { return { cmd: 'py', args: ['-3'], label: 'pyLauncher' }; }
  return { cmd: 'python3', args: [], label: 'python3' };
}
function preflightEco2AI(py: { cmd: string; args: string[] }): Promise<boolean> {
  return new Promise((resolve) => {
    const args = [...py.args, '-c', 'import importlib; import sys; importlib.import_module("eco2ai"); print("OK")'];
    execFile(py.cmd, args, { timeout: 15000 }, (err, stdout) => {
      if (err) { resolve(false); return; }
      resolve(/OK/.test(String(stdout)));
    });
  });
}

/* ===== Runner Eco2AI ===== */
async function runEco2AI(apiPath: string, code: string, interpInfo: string, py: { cmd: string; args: string[] }): Promise<string> {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'green_code_'));
  const codeFile = path.join(tmpDir, 'snippet.py');
  fs.writeFileSync(codeFile, code, 'utf8');

  try {
    const { stdout, stderr } = await execFileAsync(py.cmd, [...py.args, apiPath, codeFile], {
      shell: process.platform === 'win32' && py.cmd === 'py',
      timeout: 120000
    });
    const out = (stdout ?? '').toString().trim();
    const err = (stderr ?? '').toString().trim();

    let payload: Eco2Payload | null = null;
    let kg = Number.NaN;
    try {
      payload = JSON.parse(out) as Eco2Payload;
      if (typeof payload.emissions_kg === 'number') { kg = payload.emissions_kg; }
    } catch {
      const f = parseFloat(out);
      if (isFinite(f)) { kg = f; }
      payload = {};
    }

    const headline = !Number.isNaN(kg)
      ? (kg > 0 && kg < 1e-5 ? `${kg.toExponential(2)} kgCO₂` : `${kg.toFixed(5)} kgCO₂`)
      : (err ? `Erreur : ${err}` : 'Empreinte : indisponible');

    return buildReport(code, payload, headline, interpInfo);
  } finally {
    try { fs.rmSync(tmpDir, { recursive: true, force: true }); } catch { /* noop */ }
  }
}

/* ===== Rapport ===== */
function buildReport(code: string, m: Eco2Payload | null, headline: string, interpInfo: string): string {
  const lang = detectLanguage(code);
  const frameworks = lang === 'python' ? detectFrameworksPython(code) : [];
  const smells = lang === 'python' ? detectEnergySmellsPython(code) : [];
  const recos = quickSuggestions(smells, frameworks);

  const lines: string[] = [
    `Langage : ${lang}`,
    `Frameworks : ${frameworks.join(', ') || '—'}`,
    `Interpréteur : ${interpInfo}`,
    `Empreinte carbone estimée : ${headline}`
  ];

  if (m) {
    const duration = fmtNum(m.duration_s);
    const energy   = fmtNum(m.energy_kwh, (v) => `${v.toExponential(3)} kWh`);
    const co2g     = fmtNum(m.co2eq_g, (v) => `${v.toFixed(3)} g`);

    if (duration !== '—') { lines.push(`Durée : ${duration} s`); }
    if (energy   !== '—') { lines.push(`Énergie totale : ${energy}`); }
    if (co2g     !== '—') { lines.push(`CO₂eq total : ${co2g}`); }
    if (typeof m.stderr === 'string' && m.stderr.trim()) { lines.push(`Notes :\n${m.stderr.trim()}`); }
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

      const py = resolvePython();
      const interpInfo = `${py.cmd} ${py.args.join(' ')}`.trim();

      try {
        const ok = await preflightEco2AI(py);
        if (!ok) {
          const pipCmd = (py.cmd === 'py')
            ? 'py -3 -m pip install --upgrade pip eco2ai psutil'
            : `"${py.cmd}" -m pip install --upgrade pip eco2ai psutil`;
          const tip = [
            'Eco2AI introuvable dans l’interpréteur sélectionné.',
            `Interpréteur : ${interpInfo || '(inconnu)'}`,
            'Installe-le avec :',
            `  ${pipCmd}`,
            'Puis relance l’analyse (ou fais "Python: Select Interpreter").'
          ].join('\n');

          const analysisBlock =
            'Analyse de l’empreinte carbone du code\n' +
            '-------------------------------------\n' +
            `Empreinte carbone estimée : Erreur\n` +
            `Notes :\n${tip}`;

          webviewView.webview.postMessage({ command: 'analysisResult', result: analysisBlock });
          return;
        }

        const apiPath = path.join(this._uri.fsPath, 'src', 'eco2ai-api.py');
        const report = await runEco2AI(apiPath, code, interpInfo, py);
        webviewView.webview.postMessage({ command: 'analysisResult', result: report });
      } catch (e: unknown) {
        const m = e instanceof Error ? e.message : String(e);
        webviewView.webview.postMessage({ command: 'analysisResult', result: `Analyse indisponible : ${m}` });
      }
    });
    this._subs.push(sub);
    webviewView.onDidDispose(() => { this.dispose(); });
  }

  public dispose(): void {
    while (this._subs.length) {
      const d = this._subs.pop();
      try { if (d) { d.dispose(); } } catch { /* noop */ }
    }
  }

  private _html(): string {
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
