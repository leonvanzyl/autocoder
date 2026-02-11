/**
 * AutoForge CLI
 * =============
 *
 * Main CLI module for the AutoForge npm global package.
 * Handles Python detection, virtual environment management,
 * config loading, and uvicorn server lifecycle.
 *
 * Uses only Node.js built-in modules -- no external dependencies.
 */

import { execFileSync, spawn, execSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { existsSync, readFileSync, writeFileSync, mkdirSync, unlinkSync, rmSync, copyFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { createServer } from 'node:net';
import { homedir, platform } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

// ---------------------------------------------------------------------------
// Path constants
// ---------------------------------------------------------------------------

/** Root of the autoforge npm package (one level up from lib/) */
const PKG_DIR = dirname(dirname(fileURLToPath(import.meta.url)));

/** User config home: ~/.autoforge/ */
const CONFIG_HOME = join(homedir(), '.autoforge');

/** Virtual-environment directory managed by the CLI */
const VENV_DIR = join(CONFIG_HOME, 'venv');

/** Composite marker written after a successful pip install */
const DEPS_MARKER = join(VENV_DIR, '.deps-installed');

/** PID file for the running server */
const PID_FILE = join(CONFIG_HOME, 'server.pid');

/** Path to the production requirements file inside the package */
const REQUIREMENTS_FILE = join(PKG_DIR, 'requirements-prod.txt');

/** Path to the .env example shipped with the package */
const ENV_EXAMPLE = join(PKG_DIR, '.env.example');

/** User .env config file */
const ENV_FILE = join(CONFIG_HOME, '.env');

const IS_WIN = platform() === 'win32';

// ---------------------------------------------------------------------------
// Package version (read lazily via createRequire)
// ---------------------------------------------------------------------------

const require = createRequire(import.meta.url);
const { version: VERSION } = require(join(PKG_DIR, 'package.json'));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Indented console output matching the spec format. */
function log(msg = '') {
  console.log(`  ${msg}`);
}

/** Print a fatal error and exit. */
function die(msg) {
  console.error(`\n  Error: ${msg}\n`);
  process.exit(1);
}

/**
 * Parse a Python version string like "Python 3.13.6" and return
 * { major, minor, patch, raw } or null on failure.
 */
function parsePythonVersion(raw) {
  const m = raw.match(/Python\s+(\d+)\.(\d+)\.(\d+)/);
  if (!m) return null;
  return {
    major: Number(m[1]),
    minor: Number(m[2]),
    patch: Number(m[3]),
    raw: `${m[1]}.${m[2]}.${m[3]}`,
  };
}

/**
 * Try a single Python candidate. Returns { exe, version } or null.
 * `candidate` is either a bare name or an array of args (e.g. ['py', '-3']).
 */
function tryPythonCandidate(candidate) {
  const args = Array.isArray(candidate) ? candidate : [candidate];
  const exe = args[0];
  const extraArgs = args.slice(1);

  try {
    const out = execFileSync(exe, [...extraArgs, '--version'], {
      encoding: 'utf8',
      timeout: 10_000,
      stdio: ['pipe', 'pipe', 'pipe'],
    });

    const ver = parsePythonVersion(out);
    if (!ver) return null;

    // Require 3.11+
    if (ver.major < 3 || (ver.major === 3 && ver.minor < 11)) {
      return { exe: args.join(' '), version: ver, tooOld: true };
    }

    return { exe: args.join(' '), version: ver, tooOld: false };
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// Python detection
// ---------------------------------------------------------------------------

/**
 * Find a suitable Python >= 3.11 interpreter.
 *
 * Search order is platform-dependent:
 *   Windows:     python -> py -3 -> python3
 *   macOS/Linux: python3 -> python
 *
 * The AUTOFORGE_PYTHON env var overrides automatic detection.
 *
 * After finding a candidate we also verify that the venv module is
 * available (Debian/Ubuntu strip it out of the base package).
 */
function findPython() {
  // Allow explicit override via environment variable
  const override = process.env.AUTOFORGE_PYTHON;
  if (override) {
    const result = tryPythonCandidate(override);
    if (!result) {
      die(`AUTOFORGE_PYTHON is set to "${override}" but it could not be executed.`);
    }
    if (result.tooOld) {
      die(
        `Python ${result.version.raw} found (via AUTOFORGE_PYTHON), but 3.11+ required.\n` +
        '  Install Python 3.11+ from https://python.org'
      );
    }
    return result;
  }

  // Platform-specific candidate order
  const candidates = IS_WIN
    ? ['python', ['py', '-3'], 'python3']
    : ['python3', 'python'];

  let bestTooOld = null;

  for (const candidate of candidates) {
    const result = tryPythonCandidate(candidate);
    if (!result) continue;

    if (result.tooOld) {
      // Remember the first "too old" result for a better error message
      if (!bestTooOld) bestTooOld = result;
      continue;
    }

    // Verify venv module is available (Debian/Ubuntu may need python3-venv)
    try {
      const exeParts = result.exe.split(' ');
      execFileSync(exeParts[0], [...exeParts.slice(1), '-c', 'import ensurepip'], {
        encoding: 'utf8',
        timeout: 10_000,
        stdio: ['pipe', 'pipe', 'pipe'],
      });
    } catch {
      die(
        `Python venv module not available.\n` +
        `  Run: sudo apt install python3.${result.version.minor}-venv`
      );
    }

    return result;
  }

  // Provide the most helpful error message we can
  if (bestTooOld) {
    die(
      `Python ${bestTooOld.version.raw} found, but 3.11+ required.\n` +
      '  Install Python 3.11+ from https://python.org'
    );
  }
  die(
    'Python 3.11+ required but not found.\n' +
    '  Install from https://python.org'
  );
}

// ---------------------------------------------------------------------------
// Venv management
// ---------------------------------------------------------------------------

/** Return the path to the Python executable inside the venv. */
function venvPython() {
  return IS_WIN
    ? join(VENV_DIR, 'Scripts', 'python.exe')
    : join(VENV_DIR, 'bin', 'python');
}

/** SHA-256 hash of the requirements-prod.txt file contents. */
function requirementsHash() {
  const content = readFileSync(REQUIREMENTS_FILE, 'utf8');
  return createHash('sha256').update(content).digest('hex');
}

/**
 * Read the composite deps marker. Returns the parsed JSON object
 * or null if the file is missing / corrupt.
 */
function readMarker() {
  try {
    return JSON.parse(readFileSync(DEPS_MARKER, 'utf8'));
  } catch {
    return null;
  }
}

/**
 * Ensure the virtual environment exists and dependencies are installed.
 * Returns true if all setup steps were already satisfied (fast path).
 *
 * @param {object} python - The result of findPython()
 * @param {boolean} forceRecreate - If true, delete and recreate the venv
 */
function ensureVenv(python, forceRecreate) {
  mkdirSync(CONFIG_HOME, { recursive: true });

  const marker = readMarker();
  const reqHash = requirementsHash();
  const pyExe = venvPython();

  // Determine if the venv itself needs to be (re)created
  let needsCreate = forceRecreate || !existsSync(pyExe);

  if (!needsCreate && marker) {
    // Recreate if Python major.minor changed
    const markerMinor = marker.python_version;
    const currentMinor = `${python.version.major}.${python.version.minor}`;
    if (markerMinor && markerMinor !== currentMinor) {
      needsCreate = true;
    }

    // Recreate if the recorded python path no longer exists
    if (marker.python_path && !existsSync(marker.python_path)) {
      needsCreate = true;
    }
  }

  let depsUpToDate = false;
  if (!needsCreate && marker && marker.requirements_hash === reqHash) {
    depsUpToDate = true;
  }

  // Fast path: nothing to do
  if (!needsCreate && depsUpToDate) {
    return true;
  }

  // --- Slow path: show setup progress ---

  log('[2/3] Setting up environment...');

  if (needsCreate) {
    if (existsSync(VENV_DIR)) {
      log('      Removing old virtual environment...');
      rmSync(VENV_DIR, { recursive: true, force: true });
    }

    log(`      Creating virtual environment at ~/.autoforge/venv/`);
    const exeParts = python.exe.split(' ');
    try {
      execFileSync(exeParts[0], [...exeParts.slice(1), '-m', 'venv', VENV_DIR], {
        encoding: 'utf8',
        timeout: 120_000,
        stdio: ['pipe', 'pipe', 'pipe'],
      });
    } catch (err) {
      die(`Failed to create virtual environment: ${err.message}`);
    }
  }

  // Install / update dependencies
  log('      Installing dependencies...');
  try {
    execFileSync(pyExe, ['-m', 'pip', 'install', '-q', '--upgrade', 'pip'], {
      encoding: 'utf8',
      timeout: 300_000,
      stdio: ['pipe', 'pipe', 'pipe'],
    });

    execFileSync(pyExe, ['-m', 'pip', 'install', '-q', '-r', REQUIREMENTS_FILE], {
      encoding: 'utf8',
      timeout: 600_000,
      stdio: ['pipe', 'pipe', 'pipe'],
    });
  } catch (err) {
    die(`Failed to install dependencies: ${err.message}`);
  }

  // Write marker only after pip succeeds to prevent partial state
  const markerData = {
    requirements_hash: reqHash,
    python_version: `${python.version.major}.${python.version.minor}`,
    python_path: pyExe,
    created_at: new Date().toISOString(),
  };
  writeFileSync(DEPS_MARKER, JSON.stringify(markerData, null, 2), 'utf8');

  log('      Done');
  return false;
}

// ---------------------------------------------------------------------------
// Config (.env) management
// ---------------------------------------------------------------------------

/**
 * Parse a .env file into a plain object.
 * Handles comments, blank lines, and quoted values.
 */
function parseEnvFile(filePath) {
  const env = {};
  if (!existsSync(filePath)) return env;

  const lines = readFileSync(filePath, 'utf8').split('\n');
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;

    const eqIdx = trimmed.indexOf('=');
    if (eqIdx === -1) continue;

    const key = trimmed.slice(0, eqIdx).trim();
    let value = trimmed.slice(eqIdx + 1).trim();

    // Strip matching quotes (single or double)
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }

    if (key) {
      env[key] = value;
    }
  }
  return env;
}

/**
 * Ensure ~/.autoforge/.env exists. On first run, copy .env.example
 * from the package directory and print a notice.
 *
 * Returns true if the file was newly created.
 */
function ensureEnvFile() {
  if (existsSync(ENV_FILE)) return false;

  mkdirSync(CONFIG_HOME, { recursive: true });

  if (existsSync(ENV_EXAMPLE)) {
    copyFileSync(ENV_EXAMPLE, ENV_FILE);
  } else {
    // Fallback: create a minimal placeholder
    writeFileSync(ENV_FILE, '# AutoForge configuration\n# See documentation for available options.\n', 'utf8');
  }
  return true;
}

// ---------------------------------------------------------------------------
// Port detection
// ---------------------------------------------------------------------------

/**
 * Find an available TCP port starting from `start`.
 * Tries by actually binding a socket (most reliable cross-platform approach).
 */
function findAvailablePort(start = 8888, maxAttempts = 20) {
  for (let port = start; port < start + maxAttempts; port++) {
    try {
      const server = createServer();
      // Use a synchronous-like approach: try to listen, then close immediately
      const result = new Promise((resolve, reject) => {
        server.once('error', reject);
        server.listen(port, '127.0.0.1', () => {
          server.close(() => resolve(port));
        });
      });
      // We cannot await here (sync context), so use the blocking approach:
      // Try to bind synchronously using a different technique.
      server.close();
    } catch {
      // fall through
    }
  }
  // Synchronous fallback: try to connect; if connection refused, port is free.
  for (let port = start; port < start + maxAttempts; port++) {
    try {
      execFileSync(process.execPath, [
        '-e',
        `const s=require("net").createServer();` +
        `s.listen(${port},"127.0.0.1",()=>{s.close();process.exit(0)});` +
        `s.on("error",()=>process.exit(1))`,
      ], { timeout: 3000, stdio: 'pipe' });
      return port;
    } catch {
      continue;
    }
  }
  die(`No available ports found in range ${start}-${start + maxAttempts - 1}`);
}

// ---------------------------------------------------------------------------
// PID file management
// ---------------------------------------------------------------------------

/** Read PID from the PID file. Returns the PID number or null. */
function readPid() {
  try {
    const content = readFileSync(PID_FILE, 'utf8').trim();
    const pid = Number(content);
    return Number.isFinite(pid) && pid > 0 ? pid : null;
  } catch {
    return null;
  }
}

/** Check whether a process with the given PID is still running. */
function isProcessAlive(pid) {
  try {
    process.kill(pid, 0); // signal 0 = existence check
    return true;
  } catch {
    return false;
  }
}

/** Write the PID file. */
function writePid(pid) {
  mkdirSync(CONFIG_HOME, { recursive: true });
  writeFileSync(PID_FILE, String(pid), 'utf8');
}

/** Remove the PID file. */
function removePid() {
  try {
    unlinkSync(PID_FILE);
  } catch {
    // Ignore -- file may already be gone
  }
}

// ---------------------------------------------------------------------------
// Browser opening
// ---------------------------------------------------------------------------

/** Open a URL in the user's default browser (best-effort). */
function openBrowser(url) {
  try {
    if (IS_WIN) {
      // "start" is a cmd built-in; the empty title string avoids
      // issues when the URL contains special characters.
      execSync(`start "" "${url}"`, { stdio: 'ignore' });
    } else if (platform() === 'darwin') {
      execFileSync('open', [url], { stdio: 'ignore' });
    } else {
      // Linux: only attempt if a display server is available and
      // we are not in an SSH session.
      const hasDisplay = process.env.DISPLAY || process.env.WAYLAND_DISPLAY;
      const isSSH = !!process.env.SSH_TTY;
      if (hasDisplay && !isSSH) {
        execFileSync('xdg-open', [url], { stdio: 'ignore' });
      }
    }
  } catch {
    // Non-fatal: user can open the URL manually
  }
}

/** Detect headless / CI environments where opening a browser is pointless. */
function isHeadless() {
  if (process.env.CI) return true;
  if (process.env.CODESPACES) return true;
  if (process.env.SSH_TTY) return true;
  // Linux without a display server
  if (!IS_WIN && platform() !== 'darwin' && !process.env.DISPLAY && !process.env.WAYLAND_DISPLAY) {
    return true;
  }
  return false;
}

// ---------------------------------------------------------------------------
// Process cleanup
// ---------------------------------------------------------------------------

/** Kill a process tree. On Windows uses taskkill; elsewhere sends SIGTERM. */
function killProcess(pid) {
  try {
    if (IS_WIN) {
      execSync(`taskkill /pid ${pid} /t /f`, { stdio: 'ignore' });
    } else {
      process.kill(pid, 'SIGTERM');
    }
  } catch {
    // Process may already be gone
  }
}

// ---------------------------------------------------------------------------
// Playwright CLI
// ---------------------------------------------------------------------------

/**
 * Ensure playwright-cli is available globally for browser automation.
 * Returns true if available (already installed or freshly installed).
 *
 * @param {boolean} showProgress - If true, print install progress
 */
function ensurePlaywrightCli(showProgress) {
  try {
    execSync('playwright-cli --version', {
      timeout: 10_000,
      stdio: ['pipe', 'pipe', 'pipe'],
    });
    return true;
  } catch {
    // Not installed — try to install
  }

  if (showProgress) {
    log('      Installing playwright-cli for browser automation...');
  }
  try {
    execSync('npm install -g @playwright/cli', {
      timeout: 120_000,
      stdio: ['pipe', 'pipe', 'pipe'],
    });
    return true;
  } catch {
    return false;
  }
}

// ---------------------------------------------------------------------------
// CLI commands
// ---------------------------------------------------------------------------

function printVersion() {
  console.log(`autoforge v${VERSION}`);
}

function printHelp() {
  console.log(`
  AutoForge v${VERSION}
  Autonomous coding agent with web UI

  Usage:
    autoforge                       Start the server (default)
    autoforge config                Open ~/.autoforge/.env in $EDITOR
    autoforge config --path         Print config file path
    autoforge config --show         Show effective configuration

  Options:
    --port PORT                     Custom port (default: auto from 8888)
    --host HOST                     Custom host (default: 127.0.0.1)
    --no-browser                    Don't auto-open browser
    --repair                        Delete and recreate virtual environment
    --dev                           Development mode (requires cloned repo)
    --version                       Print version
    --help                          Show this help
`);
}

function handleConfig(args) {
  ensureEnvFile();

  if (args.includes('--path')) {
    console.log(ENV_FILE);
    return;
  }

  if (args.includes('--show')) {
    if (!existsSync(ENV_FILE)) {
      log('No configuration file found.');
      return;
    }
    const lines = readFileSync(ENV_FILE, 'utf8').split('\n');
    const active = lines.filter(l => {
      const t = l.trim();
      return t && !t.startsWith('#');
    });
    if (active.length === 0) {
      log('No active configuration. All lines are commented out.');
      log(`Edit: ${ENV_FILE}`);
    } else {
      for (const line of active) {
        console.log(line);
      }
    }
    return;
  }

  // Open in editor
  const editor = process.env.EDITOR || process.env.VISUAL || (IS_WIN ? 'notepad' : 'vi');
  try {
    execFileSync(editor, [ENV_FILE], { stdio: 'inherit' });
  } catch {
    log(`Could not open editor "${editor}".`);
    log(`Edit the file manually: ${ENV_FILE}`);
  }
}

// ---------------------------------------------------------------------------
// Main server start
// ---------------------------------------------------------------------------

function startServer(opts) {
  const { port: requestedPort, host, noBrowser, repair } = opts;

  // Step 1: Find Python
  const fastPath = !repair && existsSync(venvPython()) && readMarker()?.requirements_hash === requirementsHash();

  let python;
  if (fastPath) {
    // Skip the Python search header on fast path -- we already have a working venv
    python = null;
  } else {
    log(`[1/3] Checking Python...`);
    python = findPython();
    log(`      Found Python ${python.version.raw} at ${python.exe}`);
  }

  // Step 2: Ensure venv and deps
  if (!python) {
    // Fast path still needs a python reference for potential repair
    python = findPython();
  }
  const wasAlreadyReady = ensureVenv(python, repair);

  // Ensure playwright-cli for browser automation (quick check, installs once)
  if (!ensurePlaywrightCli(!wasAlreadyReady)) {
    log('');
    log('  Note: playwright-cli not available (browser automation will be limited)');
    log('  Install manually: npm install -g @playwright/cli');
    log('');
  }

  // Step 3: Config file
  const configCreated = ensureEnvFile();

  // Load .env into process.env for the spawned server
  const dotenvVars = parseEnvFile(ENV_FILE);

  // Determine port
  const port = requestedPort || findAvailablePort();

  // Check for already-running instance
  const existingPid = readPid();
  if (existingPid && isProcessAlive(existingPid)) {
    log(`AutoForge is already running at http://${host}:${port}`);
    log('Opening browser...');
    if (!noBrowser && !isHeadless()) {
      openBrowser(`http://${host}:${port}`);
    }
    return;
  }

  // Clean up stale PID file
  if (existingPid) {
    removePid();
  }

  // Show server startup step only on slow path
  if (!wasAlreadyReady) {
    log('[3/3] Starting server...');
  }

  if (configCreated) {
    log(`      Created config file: ~/.autoforge/.env`);
    log('      Edit this file to configure API providers (Ollama, Vertex AI, z.ai)');
    log('');
  }

  // Security warning for non-localhost host
  if (host !== '127.0.0.1') {
    console.log('');
    console.log('  !! SECURITY WARNING !!');
    console.log(`  Remote access enabled on host: ${host}`);
    console.log('  The AutoForge UI will be accessible from other machines.');
    console.log('  Ensure you understand the security implications.');
    console.log('');
  }

  // Build environment for uvicorn
  const serverEnv = { ...process.env, ...dotenvVars, PYTHONPATH: PKG_DIR };

  // Enable remote access flag for the FastAPI server
  if (host !== '127.0.0.1') {
    serverEnv.AUTOFORGE_ALLOW_REMOTE = '1';
  }

  // Spawn uvicorn
  const pyExe = venvPython();
  const child = spawn(
    pyExe,
    [
      '-m', 'uvicorn',
      'server.main:app',
      '--host', host,
      '--port', String(port),
    ],
    {
      cwd: PKG_DIR,
      env: serverEnv,
      stdio: 'inherit',
    }
  );

  writePid(child.pid);

  // Open browser after a short delay to let the server start
  if (!noBrowser && !isHeadless()) {
    setTimeout(() => openBrowser(`http://${host}:${port}`), 2000);
  }

  const url = `http://${host}:${port}`;
  console.log('');
  log(`Server running at ${url}`);
  log('Press Ctrl+C to stop');

  // Graceful shutdown handlers
  const cleanup = () => {
    killProcess(child.pid);
    removePid();
  };

  process.on('SIGINT', () => {
    console.log('');
    cleanup();
    process.exit(0);
  });

  process.on('SIGTERM', () => {
    cleanup();
    process.exit(0);
  });

  // If the child exits on its own, clean up and propagate the exit code
  child.on('exit', (code) => {
    removePid();
    process.exit(code ?? 1);
  });
}

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

/**
 * Main CLI entry point.
 *
 * @param {string[]} args - Command-line arguments (process.argv.slice(2))
 */
export function run(args) {
  // --version / -v
  if (args.includes('--version') || args.includes('-v')) {
    printVersion();
    return;
  }

  // --help / -h
  if (args.includes('--help') || args.includes('-h')) {
    printHelp();
    return;
  }

  // --dev guard: this only works from a cloned repository
  if (args.includes('--dev')) {
    die(
      'Dev mode requires a cloned repository.\n' +
      '  Clone from https://github.com/paperlinguist/autocoder and run start_ui.sh'
    );
    return;
  }

  // "config" subcommand
  if (args[0] === 'config') {
    handleConfig(args.slice(1));
    return;
  }

  // Parse flags for server start
  const host = getFlagValue(args, '--host') || '127.0.0.1';
  const portStr = getFlagValue(args, '--port');
  const port = portStr ? Number(portStr) : null;
  const noBrowser = args.includes('--no-browser');
  const repair = args.includes('--repair');

  if (port !== null && (!Number.isFinite(port) || port < 1 || port > 65535)) {
    die('Invalid port number. Must be between 1 and 65535.');
  }

  // Print banner
  console.log('');
  log(`AutoForge v${VERSION}`);
  console.log('');

  startServer({ port, host, noBrowser, repair });
}

// ---------------------------------------------------------------------------
// Argument parsing helpers
// ---------------------------------------------------------------------------

/**
 * Extract the value following a flag from the args array.
 * E.g. getFlagValue(['--port', '9000', '--host', '0.0.0.0'], '--port') => '9000'
 */
function getFlagValue(args, flag) {
  const idx = args.indexOf(flag);
  if (idx === -1 || idx + 1 >= args.length) return null;
  return args[idx + 1];
}
