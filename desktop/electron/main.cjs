const { app, BrowserWindow, ipcMain, dialog, shell, Notification } = require('electron');
const fs = require('node:fs/promises');
const path = require('node:path');
const { spawn } = require('node:child_process');
const { randomUUID } = require('node:crypto');
const { request, normalizeServer } = require('./transport.cjs');
app.setName('Marassim');
app.setPath('userData', path.join(app.getPath('appData'), 'Marassim'));

let window, config = {}, sessionToken, currentUser, pendingPair, syncRunning = false;
let onlineRunning = false;
const cloudPath = () => path.join(directory(), 'cloud.json');
async function onlineStatus() {
  requireAdmin();
  let connection = {}, status = {};
  try { connection = JSON.parse(await fs.readFile(cloudPath(), 'utf8')); } catch {}
  try { status = JSON.parse(await fs.readFile(path.join(directory(), 'online-status.json'), 'utf8')); } catch {}
  return { ...status, configured: !!connection.relayToken, onlineUrl: connection.onlineUrl, running: onlineRunning };
}
async function syncOnline() {
  if (onlineRunning) return { running: true };
  onlineRunning = true;
  try { await runServerCommand(['--online-sync', cloudPath()]); return { ok: true }; }
  finally { onlineRunning = false; }
}
async function configureOnline(value) {
  requireAdmin();
  if (config.mode !== 'client') throw new Error('Configurez le relais sur un poste client connecté à Internet.');
  const url = new URL(value.onlineUrl);
  if (url.protocol !== 'https:' || url.username || url.password || url.pathname !== '/' || url.search || url.hash) throw new Error('Indiquez uniquement l’adresse HTTPS du site.');
  let old = {};
  try { old = JSON.parse(await fs.readFile(cloudPath(), 'utf8')); } catch {}
  const secret = value.syncSecret || old.syncSecret;
  if (typeof secret !== 'string' || secret.length < 32) throw new Error('La clé doit contenir au moins 32 caractères.');
  const name = config.cloudRelayName || `${require('node:os').hostname().slice(0,45)}-${randomUUID().slice(0,8)}`;
  const result = await api('/cloud/agents', { method: 'POST', body: { name } });
  await fs.writeFile(cloudPath() + '.tmp', JSON.stringify({ onlineUrl: url.origin, syncSecret: secret, serverUrl: config.serverUrl, certificate: config.certificate, relayToken: result.relayToken }, null, 2));
  await fs.rename(cloudPath() + '.tmp', cloudPath());
  config.cloudRelayName = name; await saveConfig();
  await installTasks();
  return { configured: true };
}
const devPython = process.env.MARASSIM_PYTHON || 'python';
const directory = () => app.getPath('userData');
const configPath = () => path.join(directory(), 'connection.json');
const dataDir = () => path.join(directory(), 'data');
const replicaPath = () => path.join(directory(), 'replica.json');

async function saveConfig() {
  await fs.mkdir(directory(), { recursive: true });
  const temp = configPath() + '.tmp';
  await fs.writeFile(temp, JSON.stringify(config, null, 2));
  await fs.rename(temp, configPath());
}
function serverCommand(args) {
  return app.isPackaged
    ? [path.join(process.resourcesPath, 'server', 'MarassimServer.exe'), args]
    : [devPython, [path.join(__dirname, '..', 'server', 'app.py'), ...args]];
}
function runServerCommand(args, detached = false) {
  const [command, argv] = serverCommand(args);
  return new Promise((resolve, reject) => {
    const process = spawn(command, argv, { windowsHide: true, detached, stdio: detached ? 'ignore' : ['ignore', 'ignore', 'pipe'] });
    process.once('error', reject);
    if (detached) { process.unref(); process.once('spawn', () => resolve()); }
    else {
      let error = '';
      process.stderr.on('data', chunk => { error = (error + chunk).slice(-4000); });
      process.once('exit', code => code === 0 ? resolve() : reject(new Error(error || 'L’opération n’a pas abouti.')));
    }
  });
}
async function serverStart(importExisting) {
  let source;
  if (importExisting) {
    const result = await dialog.showOpenDialog(window, { title: 'Choisir la base existante (une copie sera créée)', properties: ['openFile'], filters: [{ name: 'Base Marassim', extensions: ['db'] }] });
    if (result.canceled) return { canceled: true };
    source = result.filePaths[0];
  }
  await fs.mkdir(dataDir(), { recursive: true });
  if (source) {
    try { await fs.access(path.join(dataDir(), 'marassim.db')); throw new Error('Une base serveur existe déjà. L’import est disponible uniquement lors de la première installation.'); }
    catch (error) { if (error.code !== 'ENOENT') throw error; }
  }
  const args = ['--data-dir', dataDir()];
  if (source) args.push('--source', source);
  const localUrl = 'https://127.0.0.1:7443';
  try {
    const certificate = await fs.readFile(path.join(dataDir(), 'server.crt'), 'utf8');
    await request(localUrl, '/health', { certificate });
  } catch {
    await runServerCommand(args, true);
  }
  let health;
  for (let attempt = 0; attempt < 40; attempt++) {
    try {
      const certificate = await fs.readFile(path.join(dataDir(), 'server.crt'), 'utf8');
      health = await request(localUrl, '/health', { certificate });
      config = { ...config, mode: 'server', serverUrl: localUrl, certificate };
      break;
    } catch { await new Promise(resolve => setTimeout(resolve, 500)); }
  }
  if (!health) throw new Error('Le serveur n’a pas démarré. Consultez data/server.log dans le dossier Marassim.');
  sessionToken = currentUser = null;
  await saveConfig();
  return { ...health, mode: 'server', serverUrl: localUrl };
}
async function sync() {
  if (syncRunning) return { running: true };
  syncRunning = true;
  try { await fs.access(replicaPath()); await runServerCommand(['--replica', replicaPath()]); return { ok: true }; }
  finally { syncRunning = false; }
}
function checkedSender(event) {
  if (!window || event.sender !== window.webContents || event.senderFrame !== window.webContents.mainFrame) throw new Error('Appel non autorisé.');
}
function register(name, handler) {
  ipcMain.handle(name, async (event, ...args) => {
    checkedSender(event);
    try { return { ok: true, value: await handler(...args) }; }
    catch (error) { return { ok: false, error: error.message, status: error.status }; }
  });
}
function requireAdmin() {
  if (!sessionToken || currentUser?.role !== 'admin') throw new Error('Connectez-vous avec un compte administrateur.');
}
async function api(pathname, options = {}) {
  if (!config.serverUrl) throw new Error('Configurez la connexion au serveur.');
  const method = options.method || 'GET';
  if (!['GET', 'POST', 'PUT', 'DELETE'].includes(method)) throw new Error('Méthode invalide.');
  let bootstrap;
  if (pathname === '/setup' && config.mode === 'server') bootstrap = await fs.readFile(path.join(dataDir(), 'bootstrap.key'), 'utf8');
  const result = await request(config.serverUrl, pathname, { method, body: options.body, certificate: config.certificate, token: sessionToken, bootstrap, idempotencyKey: options.idempotencyKey || (method === 'GET' ? undefined : randomUUID()) });
  if (pathname === '/login') {
    sessionToken = result.token; currentUser = result.user;
    return { user: result.user };
  }
  if (pathname === '/me') currentUser = result;
  return result;
}
async function saveFile(file) {
  if (!file || typeof file.base64 !== 'string' || file.base64.length > 90 * 1024 * 1024 || !/\.(xlsx|docx)$/.test(file.name)) throw new Error('Fichier invalide.');
  const name = path.basename(file.name).replace(/[<>:"/\\|?*]/g, '_');
  const result = await dialog.showSaveDialog(window, { defaultPath: path.join(app.getPath('documents'), name), filters: [{ name: 'Document Marassim', extensions: [name.split('.').pop()] }] });
  if (result.canceled) return { canceled: true };
  await fs.writeFile(result.filePath, Buffer.from(file.base64, 'base64'));
  await shell.openPath(result.filePath);
  return { saved: true };
}
async function installTasks() {
  requireAdmin();
  if (!app.isPackaged) throw new Error('Les tâches automatiques s’installent depuis la version Windows compilée.');
  const script = path.join(process.resourcesPath, 'install-tasks.ps1');
  const [executable] = serverCommand([]);
  const args = ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', script, '-ServerExe', executable, '-ConfigDirectory', directory(), '-Mode', config.mode];
  // Current-user tasks do not require elevation; all paths are structured arguments.
  await new Promise((resolve, reject) => {
    const child = spawn('powershell.exe', args, { windowsHide: true, stdio: ['ignore', 'ignore', 'pipe'] });
    let errors = '';
    child.stderr.on('data', data => { errors = (errors + data).slice(-4000); });
    child.on('error', reject);
    child.on('exit', code => code === 0 ? resolve() : reject(new Error(errors || 'Impossible d’installer les tâches Windows.')));
  });
  return { ok: true };
}

async function initialize() {
  try { config = JSON.parse(await fs.readFile(configPath(), 'utf8')); } catch { config = {}; }
  register('config:get', () => ({ mode: config.mode, serverUrl: config.serverUrl, configured: !!config.certificate, replicaName: config.replicaName }));
  register('config:reset', async () => {
    sessionToken = currentUser = pendingPair = null;
    // Preserve backup task credentials until a new server is explicitly paired.
    await fs.unlink(cloudPath()).catch(() => {});
    config = {}; await saveConfig(); return { ok: true };
  });
  register('server:start', serverStart);
  register('server:probe', async url => { pendingPair = await request(normalizeServer(url), '/health', { probe: true }); return pendingPair; });
  register('server:pair', async () => {
    if (!pendingPair) throw new Error('Vérifiez d’abord l’adresse du serveur.');
    config = { mode: 'client', serverUrl: pendingPair.serverUrl, certificate: pendingPair.certificate };
    sessionToken = currentUser = null;
    await fs.unlink(replicaPath()).catch(() => {});
    await fs.unlink(cloudPath()).catch(() => {});
    await saveConfig(); pendingPair = null; return { ok: true };
  });
  register('api:request', api);
  register('session:logout', async () => { try { await api('/logout', { method: 'POST' }); } finally { sessionToken = currentUser = null; } });
  register('file:save', saveFile);
  register('notification:show', value => {
    if (!sessionToken || !currentUser) throw new Error('Connectez-vous avant de recevoir les notifications.');
    if (!value || typeof value.title !== 'string' || typeof value.body !== 'string' || value.title.length > 120 || value.body.length > 300) throw new Error('Notification invalide.');
    if (Notification.isSupported()) new Notification({ title: value.title, body: value.body, icon: path.join(__dirname, '..', 'assets', 'marassim-logo.png') }).show();
    return { ok: true };
  });
  register('online:status', onlineStatus);
  register('online:configure', configureOnline);
  register('online:sync', () => { requireAdmin(); return syncOnline(); });
  register('replica:enable', async name => {
    requireAdmin();
    if (config.mode !== 'client') throw new Error('La copie serveur est déjà créée automatiquement sur ce PC.');
    const result = await api('/replicas', { method: 'POST', body: { name } });
    const backupDirectory = path.join(directory(), 'backups');
    await fs.writeFile(replicaPath(), JSON.stringify({ serverUrl: config.serverUrl, certificate: config.certificate, replicaToken: result.replicaToken, backupDirectory }, null, 2));
    config.replicaName = name; await saveConfig();
    await sync(); return { ok: true, backupDirectory };
  });
  register('replica:sync', sync);
  register('recovery:export', async () => {
    requireAdmin();
    if (config.mode !== 'server') throw new Error('Exportez la clé depuis le PC serveur.');
    const result = await dialog.showSaveDialog(window, { title: 'Conserver la clé sur une clé USB séparée', defaultPath: 'Marassim-recovery.key', filters: [{ name: 'Clé de récupération', extensions: ['key'] }] });
    if (result.canceled) return { canceled: true };
    await fs.copyFile(path.join(dataDir(), 'recovery.key'), result.filePath);
    return { saved: true };
  });
  register('tasks:install', installTasks);
  window = new BrowserWindow({ width: 1440, height: 940, minWidth: 1000, minHeight: 700, title: 'Marassim', icon: path.join(__dirname, '..', 'assets', 'marassim-logo.png'), backgroundColor: '#f7f8fa', autoHideMenuBar: true, webPreferences: { preload: path.join(__dirname, 'preload.cjs'), contextIsolation: true, nodeIntegration: false, sandbox: true } });
  window.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
  window.webContents.on('will-navigate', event => event.preventDefault());
  window.webContents.session.setPermissionRequestHandler((_contents, _permission, callback) => callback(false));
  if (process.env.MARASSIM_DEV_URL) await window.loadURL('http://127.0.0.1:5173');
  else await window.loadFile(path.join(__dirname, '..', 'dist', 'index.html'));
  window.on('closed', () => { window = null; });
  const interval = setInterval(() => { if (config.replicaName) sync().catch(() => {}); }, 5 * 60 * 1000);
  interval.unref();
  const onlineInterval = setInterval(() => { if (config.mode === 'client') fs.access(cloudPath()).then(syncOnline).catch(() => {}); }, 20 * 60 * 1000);
  onlineInterval.unref();
  if (config.mode === 'client') fs.access(cloudPath()).then(syncOnline).catch(() => {});
  if (config.replicaName) sync().catch(() => {});
  if (config.mode === 'server') serverStart(false).catch(() => {});
}
if (!app.requestSingleInstanceLock()) app.quit();
else {
  app.whenReady().then(initialize).catch(error => { dialog.showErrorBox('Marassim', error.message); app.quit(); });
  app.on('second-instance', () => { if (window) { if (window.isMinimized()) window.restore(); window.focus(); } });
  app.on('window-all-closed', () => app.quit());
}
