console.log("### EXECUTING frontend/public/electron.js - VERSION XYZ ###");
const fs = require('fs');
const path = require('path');
const os = require('os');
const http = require('http');
const url = require('url');
const { createAuthServer } = require('./auth-server');
const { spawn, exec } = require('child_process');
const Store = require('electron-store');
const startupLogPath = path.join(os.homedir(), 'denker_electron_startup_log.txt');
const debugLogPath = path.join(os.homedir(), 'denker_debug_full.log');
fs.writeFileSync(startupLogPath, `Electron main process (electron.js) started at ${new Date().toISOString()}\n`, { flag: 'a' });

// Enhanced logging for debugging GUI launches
const originalConsoleLog = console.log;
const originalConsoleError = console.error;

console.log = function(...args) {
  const timestamp = new Date().toISOString();
  const message = `[${timestamp}] LOG: ${args.join(' ')}\n`;
  try {
    fs.appendFileSync(debugLogPath, message);
  } catch (e) {
    // Ignore file write errors
  }
  originalConsoleLog.apply(console, args);
};

console.error = function(...args) {
  const timestamp = new Date().toISOString();
  const message = `[${timestamp}] ERROR: ${args.join(' ')}\n`;
  try {
    fs.appendFileSync(debugLogPath, message);
  } catch (e) {
    // Ignore file write errors
  }
  originalConsoleError.apply(console, args);
};

console.log('🚀 electron.js script started. Timestamp:', Date.now());
fs.appendFileSync(startupLogPath, `Initial console.log in electron.js executed at ${new Date().toISOString()}\n`);
const { app, BrowserWindow, ipcMain, globalShortcut, screen, Tray, Menu, clipboard, dialog, desktopCapturer, protocol, shell, systemPreferences } = require('electron');
fs.appendFileSync(startupLogPath, `Electron modules imported at ${new Date().toISOString()}\n`);
const isDev = process.env.NODE_ENV === 'development';
if (isDev) {
  require('dotenv').config({ path: path.join(__dirname, '../.env') });
}

// Initialize store for app settings
const store = new Store();

// Keep a global reference of the windows and servers
let mainWindow = null;
let subWindow = null;
let tray = null;
let authServer = null;
let restartDialogWindow = null; // Added for custom dialog
let backendProc = null; // Add global reference to track the local-backend process

// Window dimensions and positions
const MAIN_WINDOW_WIDTH_RATIO = 0.25; // 1/4 of screen width
const SUB_WINDOW_WIDTH = 400;
const SUB_WINDOW_HEIGHT = 300;

// Clipboard monitoring
let lastClipboardChangeTime = 0;
let clipboardMonitorInterval = null;
let lastClipboardText = '';

// Maximum age for clipboard content (20 seconds)
const MAX_CLIPBOARD_AGE = 20000;

// Add API configuration
let API_URL;
let WS_URL;

if (isDev) {
  API_URL = process.env.VITE_API_URL_DEV || 'http://127.0.0.1:8001/api/v1';
  // Derive WS_URL from API_URL for dev to keep them in sync
  try {
    const apiUrlObj = new URL(API_URL);
    const protocol = apiUrlObj.protocol === 'https:' ? 'wss:' : 'ws:';
    WS_URL = `${protocol}//${apiUrlObj.host}`;
  } catch (e) {
    console.warn(`[electron.js] Could not parse VITE_API_URL_DEV ('${API_URL}') to derive WS_URL. Falling back to default. Error: ${e.message}`);
    WS_URL = 'ws://127.0.0.1:8001';
  }
  console.log(`[electron.js] Development URLs: API_URL=${API_URL}, WS_URL=${WS_URL}`);
} else {
  // In production, use specific PROD environment variables or fallbacks
  API_URL = process.env.VITE_API_URL_PROD || 'https://denker-backend-052025-635468353975.europe-west3.run.app/api/v1'; // Replace with your actual prod API URL
  // For WS_URL in production, you might have a different domain or it might be derived.
  // If VITE_WS_URL_PROD is explicitly set, use it. Otherwise, derive from API_URL_PROD.
  if (process.env.VITE_WS_URL_PROD) {
    WS_URL = process.env.VITE_WS_URL_PROD;
  } else {
    try {
      const apiUrlObj = new URL(API_URL); // Use the production API_URL
      const protocol = apiUrlObj.protocol === 'https:' ? 'wss:' : 'ws:';
      WS_URL = `${protocol}//${apiUrlObj.host}`;
    } catch (e) {
      console.warn(`[electron.js] Could not parse VITE_API_URL_PROD ('${API_URL}') to derive WS_URL. Falling back. Error: ${e.message}`);
      // Fallback to a placeholder or a sensible default if parsing fails
      WS_URL = 'wss://denker-backend-052025-635468353975.europe-west3.run.app'; // Replace or ensure API_URL_PROD is a valid URL
    }
  }
  console.log(`[electron.js] Production URLs: API_URL=${API_URL}, WS_URL=${WS_URL}`);
}

const API_KEY = process.env.VITE_API_KEY;

// Function to free a port
function freePort(port, callback) {
  const platform = process.platform;
  let findProcessCommand;

  console.log(`[PortManager] Attempting to free port ${port} on platform ${platform}...`);

  const execPromise = (command) => {
    return new Promise((resolve) => {
      exec(command, (err, stdout, stderr) => {
        // lsof exits with 1 if it finds no process, which is not a true error for us.
        if (err && !(stdout === '' && stderr === '' && err.code === 1)) {
          console.warn(`[PortManager] Command '${command}' may have failed: ${err.message}`);
          resolve({ err, stdout, stderr });
          return;
        }
        if (stderr) {
            console.warn(`[PortManager] Command '${command}' produced stderr: ${stderr}`);
        }
        resolve({ stdout, stderr });
      });
    });
  };

  const findAndKill = async () => {
    try {
      if (platform === 'darwin' || platform === 'linux') {
        const { stdout: pidsOut, err: lsofErr } = await execPromise(`lsof -i :${port} -t`);

        if (lsofErr && !pidsOut.trim()) {
            console.log(`[PortManager] No process found on port ${port} (lsof exited with error but no output).`);
            return callback();
        }

        const pids = pidsOut.toString().split('\n').filter(pid => pid.trim() !== '');
        
        if (pids.length > 0) {
          console.log(`[PortManager] Found PIDs on port ${port}: ${pids.join(', ')}. Attempting to kill...`);
          const killPromises = pids.map(pid => {
            console.log(`[PortManager] Sending kill -9 to PID ${pid}`);
            return execPromise(`kill -9 ${pid}`);
          });
          
          const results = await Promise.all(killPromises);
          
          results.forEach(({err}, index) => {
              if (err) {
                  console.error(`[PortManager] Failed to kill process ${pids[index]}: ${err.message}`);
              } else {
                  console.log(`[PortManager] Successfully signaled process ${pids[index]} to terminate.`);
              }
          });

          console.log(`[PortManager] Kill attempts for port ${port} finished.`);
          setTimeout(callback, 1000); // Increased delay for OS to release port
        } else {
          console.log(`[PortManager] No running process found on port ${port}.`);
          callback();
        }
      } else if (platform === 'win32') {
        findProcessCommand = `netstat -ano | findstr :${port}`;
        const { stdout: netstatOut } = await execPromise(findProcessCommand);
        const lines = netstatOut.toString().split('\n');
        let pidFound = null;
        const listeningRegex = new RegExp(`:${port}\\s+.*LISTENING\\s+(\\d+)`, 'i');

        for (const line of lines) {
            const match = line.match(listeningRegex);
            if (match && match[1]) {
            pidFound = match[1];
            break;
            }
        }

        if (pidFound) {
            console.log(`[PortManager] Process ${pidFound} found on port ${port}. Attempting to kill.`);
            await execPromise(`taskkill /PID ${pidFound} /F /T`);
            console.log(`[PortManager] Successfully killed process ${pidFound} on port ${port}`);
            setTimeout(callback, 500); // Short delay
        } else {
            console.log(`[PortManager] No process found listening on port ${port}.`);
            callback();
        }
      } else {
        console.warn(`[PortManager] Unsupported platform: ${platform}. Cannot automatically free port.`);
        callback();
      }
    } catch (error) {
        console.error(`[PortManager] An unexpected error occurred in findAndKill for port ${port}:`, error);
        callback(); // proceed anyway to not block app startup
    }
  };

  findAndKill();
}

// Store the API URLs for use in the renderer
const RENDERER_ENV_VARS = {
  VITE_API_URL: API_URL, // This will now be correctly http://127.0.0.1:8001/api/v1 in dev, or prod URL
  VITE_WS_URL: WS_URL, // This will now be correctly ws://127.0.0.1:8001 in dev, or prod URL
  VITE_API_KEY: API_KEY,
  // Add Auth0 configuration with hard-coded fallbacks for production
  VITE_AUTH0_DOMAIN: process.env.VITE_AUTH0_DOMAIN || 'auth.denker.ai',
  VITE_AUTH0_CLIENT_ID: process.env.VITE_AUTH0_CLIENT_ID || 'lq6uzeeUp9i14E8FNpJwr0DVIP5VtOzQ',
  VITE_AUTH0_AUDIENCE: process.env.VITE_AUTH0_AUDIENCE || 'https://api.denker.ai',
  VITE_NODE_ENV: isDev ? 'development' : 'production', // Correctly set NODE_ENV
  VITE_VERTEX_AI_PROJECT_ID: process.env.VITE_VERTEX_AI_PROJECT_ID || 'modular-bucksaw-424010-p6' // Add Vertex AI Project ID
};

console.log('🔧 Environment variables for renderer:', {
  VITE_API_URL: RENDERER_ENV_VARS.VITE_API_URL,
  VITE_WS_URL: RENDERER_ENV_VARS.VITE_WS_URL,
  VITE_AUTH0_DOMAIN: RENDERER_ENV_VARS.VITE_AUTH0_DOMAIN,
  VITE_AUTH0_CLIENT_ID: RENDERER_ENV_VARS.VITE_AUTH0_CLIENT_ID ? RENDERER_ENV_VARS.VITE_AUTH0_CLIENT_ID.substring(0, 8) + '...' : 'MISSING',
  VITE_AUTH0_AUDIENCE: RENDERER_ENV_VARS.VITE_AUTH0_AUDIENCE,
  VITE_NODE_ENV: RENDERER_ENV_VARS.VITE_NODE_ENV,
  VITE_VERTEX_AI_PROJECT_ID: RENDERER_ENV_VARS.VITE_VERTEX_AI_PROJECT_ID,
  isDev
});

// Parse any command line arguments
let deeplinkingUrl;

console.log('🚀 electron.js: About to attach app.whenReady() handler for main window creation. Timestamp:', Date.now());
fs.appendFileSync(startupLogPath, `app.whenReady handler attached at ${new Date().toISOString()}\n`);
app.whenReady().then(() => {
  fs.appendFileSync(startupLogPath, `app.whenReady resolved at ${new Date().toISOString()}\n`);
  console.log('🚀 electron.js: app.whenReady() for main window creation has resolved. Timestamp:', Date.now());

  // FIXED: Use consistent temp workspace location that matches chart/markdown creation
  // This ensures files created by agents are accessible by filesystem operations
  const defaultMcpFsRoot = path.join(require('os').tmpdir(), 'denker_workspace', 'default');
  try {
    if (!fs.existsSync(defaultMcpFsRoot)) {
      fs.mkdirSync(defaultMcpFsRoot, { recursive: true });
      console.log(`[electron.js] Created default MCP filesystem root: ${defaultMcpFsRoot}`);
    }
  } catch (err) {
    console.error(`[electron.js] Error creating default MCP filesystem root at ${defaultMcpFsRoot}:`, err);
  }

  // Define path for user settings file (to be managed by FastAPI, but Electron tells FastAPI where it is)
  const userSettingsFilePath = path.join(app.getPath('userData'), 'denker_user_settings.json');
  console.log(`[electron.js] User settings file path determined as: ${userSettingsFilePath}`);

  // Register ALL critical IPC handlers needed by preload/renderer at startup
  // BEFORE creating the main window.
  console.log('[*] Registering critical IPC Handlers...');

  // IPC handler to provide environment variables to the renderer
  // Cache to reduce redundant logging for env vars requests (performance optimization)
  let envVarsRequestCount = 0;
  ipcMain.handle('get-renderer-env-vars', () => {
    envVarsRequestCount++;
    // Only log the first few requests to reduce startup overhead
    if (envVarsRequestCount <= 3) {
      console.log(`[electron.js IPC] Request received for RENDERER_ENV_VARS (${envVarsRequestCount}).`);
      console.log('[electron.js IPC] Current RENDERER_ENV_VARS.VITE_WS_URL is:', RENDERER_ENV_VARS.VITE_WS_URL);
      console.log('[electron.js IPC] Current RENDERER_ENV_VARS.VITE_API_URL is:', RENDERER_ENV_VARS.VITE_API_URL);
      console.log('[electron.js IPC] Current RENDERER_ENV_VARS.VITE_NODE_ENV is:', RENDERER_ENV_VARS.VITE_NODE_ENV);
    } else if (envVarsRequestCount === 4) {
      console.log('[electron.js IPC] Further RENDERER_ENV_VARS requests will not be logged to reduce overhead...');
    }
    return RENDERER_ENV_VARS;
  });
  console.log("🔧 IPC handler 'get-renderer-env-vars' registered.");

  // IPC handler for opening directory dialog
  ipcMain.handle('dialog:openDirectory', async () => {
    if (!mainWindow) {
      console.error('Cannot show open directory dialog: mainWindow is not available.');
      return null;
    }
    const { canceled, filePaths } = await dialog.showOpenDialog(mainWindow, {
      properties: ['openDirectory']
    });
    if (canceled || filePaths.length === 0) {
      console.log('Open directory dialog was canceled or no path selected.');
      return null;
    } else {
      console.log('Directory selected:', filePaths[0]);
      return filePaths[0];
    }
  });
  console.log("📂 IPC handler 'dialog:openDirectory' registered.");

  // IPC handler for opening file dialog (for file uploads)
  ipcMain.handle('dialog:openFile', async () => {
    if (!mainWindow) {
      console.error('Cannot show open file dialog: mainWindow is not available.');
      return null;
    }
    const { canceled, filePaths } = await dialog.showOpenDialog(mainWindow, {
      properties: ['openFile', 'multiSelections'],
      filters: [
        { name: 'All Files', extensions: ['*'] },
        { name: 'Documents', extensions: ['pdf', 'doc', 'docx', 'txt', 'md'] },
        { name: 'Images', extensions: ['jpg', 'jpeg', 'png', 'gif', 'svg'] },
        { name: 'Code', extensions: ['js', 'ts', 'tsx', 'jsx', 'py', 'json', 'yaml', 'yml'] }
      ]
    });
    if (canceled || filePaths.length === 0) {
      console.log('Open file dialog was canceled or no files selected.');
      return null;
    } else {
      console.log('Files selected:', filePaths);
      return filePaths;
    }
  });
  console.log("📁 IPC handler 'dialog:openFile' registered.");

  // IPC handler for restarting the app
  ipcMain.handle('restart-app', () => {
    console.log('[electron.js IPC] Request received to restart the application.');
    app.relaunch();
    cleanupAndQuit();
  });
  console.log("🔄 IPC handler 'restart-app' registered.");

  // IPC handler for showing a restart confirmation dialog
  ipcMain.handle('show-restart-dialog', async (event, options) => {
    // Close existing custom dialog if any
    if (restartDialogWindow) {
      restartDialogWindow.close();
      restartDialogWindow = null;
    }

    const dialogOptions = {
      title: options?.title || 'Restart Required',
      message: options?.message || 'Application settings have changed.',
      detail: options?.detail || 'A restart is recommended for all changes to take effect.',
    };

    restartDialogWindow = new BrowserWindow({
      width: 380,
      height: 270,
      parent: mainWindow, // Make it a child of the main window
      modal: true,       // Make it modal to the parent
      frame: false,
      transparent: true,
      show: false,
      skipTaskbar: true,
      resizable: false,
      webPreferences: {
        preload: path.join(__dirname, 'preload-dialog.js'),
        nodeIntegration: false,
        contextIsolation: true,
      },
    });

    const queryParams = new URLSearchParams(dialogOptions).toString();
    const dialogUrl = isDev
      ? `http://localhost:5173/restart-dialog.html?${queryParams}`
      : `file://${path.join(__dirname, 'restart-dialog.html')}?${queryParams}`;

    restartDialogWindow.loadURL(dialogUrl);

    // No menu for this dialog
    restartDialogWindow.setMenu(null);

    return new Promise((resolve) => {
      // Listen for response from the dialog window
      ipcMain.once('custom-restart-dialog-response', (event, action) => {
        if (restartDialogWindow && !restartDialogWindow.isDestroyed()) {
          restartDialogWindow.close();
        }
        restartDialogWindow = null;

        if (action === 'restart') {
          console.log('[electron.js IPC] User chose to restart now from custom dialog. Delaying for 1 second.');
          setTimeout(() => {
            console.log('[electron.js IPC] Restarting application after 1-second delay.');
            app.relaunch();
            cleanupAndQuit();
          }, 1000); // 1000 milliseconds = 1 second
          resolve({ response: 0 }); // Corresponds to 'Restart Now'
        } else { // 'later' or closed
          console.log('[electron.js IPC] User chose "Later" or closed the custom dialog.');
          resolve({ response: 1 }); // Corresponds to 'Later'
        }
      });

      restartDialogWindow.once('ready-to-show', () => {
          if (restartDialogWindow) restartDialogWindow.show();
      });

      restartDialogWindow.on('closed', () => {
        // If the window is closed without a choice (e.g., via DevTools), treat as 'later'
        ipcMain.removeHandler('custom-restart-dialog-response'); // Clean up listener
        if (restartDialogWindow) { // Check if it wasn't already nullified by a choice
           resolve({ response: 1 }); // Corresponds to 'Later'
        }
        restartDialogWindow = null;
      });
    });
  });
  console.log("💬 IPC handler 'show-restart-dialog' registered (now uses custom window).");

  // IPC handler for restarting local backend (placeholder, as app restart is preferred for now)
  // COMMENTED OUT: This was causing multiple backend processes to be spawned
  // The main backend spawning logic during app startup is sufficient
  /*
  ipcMain.handle('request-restart-local-backend', async () => {
    console.log('[electron.js IPC] Received request to restart local backend. Implementing proper restart...');
    
    try {
      // Kill existing backend process
      if (backendProc) {
        console.log(`[electron.js] Killing existing backend process (PID: ${backendProc.pid})`);
        backendProc.kill('SIGTERM');
        
        // Wait for process to exit
        await new Promise((resolve) => {
          if (backendProc) {
            backendProc.on('close', resolve);
            setTimeout(resolve, 3000); // Timeout after 3 seconds
          } else {
            resolve();
          }
        });
        
        backendProc = null;
      }
      
      // Only restart in production mode
      if (!isDev) {
        // Re-spawn the backend using the same logic as startup
        const resourcesBinDir = path.join(process.resourcesPath, 'bin');
        const backendExecutableName = process.platform === 'win32' ? 'local-backend-pkg.exe' : 'local-backend-pkg';
        const backendPath = path.join(process.resourcesPath, 'local-backend-pkg', backendExecutableName);
        
        // Use the same environment as startup
        const backendEnv = {
          ...process.env,
          DENKER_USER_SETTINGS_PATH: path.join(app.getPath('userData'), 'denker_user_settings.json'),
          VITE_API_URL: RENDERER_ENV_VARS.VITE_API_URL,
          AUTH0_DOMAIN: RENDERER_ENV_VARS.VITE_AUTH0_DOMAIN,
          AUTH0_API_AUDIENCE: RENDERER_ENV_VARS.VITE_AUTH0_AUDIENCE,
          AUTH0_CLIENT_ID: RENDERER_ENV_VARS.VITE_AUTH0_CLIENT_ID,
          VERTEX_AI_PROJECT_ID: RENDERER_ENV_VARS.VITE_VERTEX_AI_PROJECT_ID,
          VERTEX_AI_LOCATION: 'europe-west4',
          NODE_ENV: RENDERER_ENV_VARS.VITE_NODE_ENV,
          QDRANT_URL: 'https://f1f12584-e161-4974-b6fa-eb2e8bc3fdfc.europe-west3-0.gcp.cloud.qdrant.io',
          QDRANT_API_KEY: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.u7ZjD6dc0cEIMMX2ZxDHio-xD1IIjwYaTSm3PZ-dLEE',
          QDRANT_COLLECTION_NAME: 'denker_embeddings',
          EMBEDDING_MODEL: 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2',
          VECTOR_NAME: 'fast-paraphrase-multilingual-minilm-l12-v2',
          ANTHROPIC_API_KEY: "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",
          DENKER_DEV_MODE: 'false', // Explicitly set for production
          DENKER_COORDINATOR_TIMEOUT_SECONDS: '120' // Set coordinator timeout to 2 minutes (120 seconds)
        };
        
        // Free port and restart
        freePort(9001, () => {
          console.log('[electron.js] Restarting local-backend-pkg...');
          backendProc = spawn(backendPath, [], { stdio: 'inherit', env: backendEnv });
          
          backendProc.on('error', (spawnError) => {
            console.error(`[electron.js] Failed to restart local-backend-pkg: ${spawnError.message}`);
            backendProc = null;
          });
          
          backendProc.on('close', (code) => {
            console.log(`Restarted local-backend-pkg exited with code ${code}`);
            backendProc = null;
          });
          
          if (backendProc && backendProc.pid) {
            console.log(`[electron.js] Local backend restarted with PID: ${backendProc.pid}`);
          }
        });
      }
      
      return { success: true, message: "Local backend restarted successfully" };
    } catch (error) {
      console.error('[electron.js] Error restarting local backend:', error);
      return { success: false, message: `Failed to restart local backend: ${error.message}` };
    }
  });
  */

  // For now, return a simple message that app restart is preferred
  ipcMain.handle('request-restart-local-backend', async () => {
    console.log('[electron.js IPC] Backend restart requested, but disabled to prevent multiple processes. App restart is preferred.');
    return { success: false, message: "Backend restart disabled. Please restart the entire app instead." };
  });

  // Setup all Auth0 related IPC handlers
  setupAuth0Authentication(); // This function will now register login, logout, get-access-token, get-user-info, dev-process-auth0-callback

  console.log('🚀 electron.js: Calling createMainWindow() after IPC handler registration. Timestamp:', Date.now());
  createMainWindow();
  registerGlobalShortcut();
  setupClipboardMonitor();
  setupAppMenu();

  // --- SPAWN LOCAL BACKEND AND MCP SERVERS IN PRODUCTION ONLY ---
  if (!isDev) {
    // Path helpers for production
    const resourcesBinDir = path.join(process.resourcesPath, 'bin'); // For pandoc, tesseract etc.
    
    // Determine the correct executable name based on platform
    // PyInstaller names the executable inside the onedir bundle the same as the --name argument.
    const backendExecutableName = process.platform === 'win32' ? 'local-backend-pkg.exe' : 'local-backend-pkg';
    // The executable is at the root of the 'local-backend-pkg' folder copied into resources.
    const backendPath = path.join(process.resourcesPath, 'local-backend-pkg', backendExecutableName);
    
    // Prepare environment for the backend process
    const backendEnv = {
      ...process.env, // Inherit current environment variables
      // Add the bin directory to PATH so backend can find pandoc, tesseract, etc.
      PATH: `${resourcesBinDir}:${process.env.PATH || '/usr/local/bin:/usr/bin:/bin'}`,
      DENKER_USER_SETTINGS_PATH: userSettingsFilePath, // Add path to user settings file
      // Pass the remote API URL that Electron is aware of (from its own env/config)
      // to the Python backend, so it knows where the remote API is.
      VITE_API_URL: RENDERER_ENV_VARS.VITE_API_URL, 
      // Pass Auth0 and Vertex AI details required by the local backend's settings
      AUTH0_DOMAIN: RENDERER_ENV_VARS.VITE_AUTH0_DOMAIN,
      AUTH0_API_AUDIENCE: RENDERER_ENV_VARS.VITE_AUTH0_AUDIENCE,
      // Note: The local backend's settings.py might expect AUTH0_CLIENT_ID if it needs to perform specific client-side Auth0 actions,
      // but typically client_id is for frontend/public clients. If local-backend needs it for *its own* interactions, add it.
      // For now, assuming AUTH0_DOMAIN and AUTH0_API_AUDIENCE are the primary ones needed by local-backend settings.
      // Let's add VITE_AUTH0_CLIENT_ID as well, as it's often useful for backend services too.
      AUTH0_CLIENT_ID: RENDERER_ENV_VARS.VITE_AUTH0_CLIENT_ID,
      VERTEX_AI_PROJECT_ID: RENDERER_ENV_VARS.VITE_VERTEX_AI_PROJECT_ID,
      VERTEX_AI_LOCATION: 'europe-west4', // Added
      NODE_ENV: RENDERER_ENV_VARS.VITE_NODE_ENV, // Pass NODE_ENV as well
      MPLBACKEND: 'Agg', // Non-interactive backend for unstructured
      MPLCONFIGDIR: path.join(require('os').tmpdir(), 'denker_matplotlib_cache'), // Writable cache directory
      VITE_NODE_ENV: RENDERER_ENV_VARS.VITE_NODE_ENV, // Pass NODE_ENV as well
      QDRANT_URL: 'https://f1f12584-e161-4974-b6fa-eb2e8bc3fdfc.europe-west3-0.gcp.cloud.qdrant.io',
      QDRANT_API_KEY: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.u7ZjD6dc0cEIMMX2ZxDHio-xD1IIjwYaTSm3PZ-dLEE',
      QDRANT_COLLECTION_NAME: 'denker_embeddings',
      EMBEDDING_MODEL: 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2',
      VECTOR_NAME: 'fast-paraphrase-multilingual-minilm-l12-v2',
      ANTHROPIC_API_KEY: "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",
      UNSPLASH_ACCESS_KEY: "Rsz5zQR6q4ogic0dVVAgBlS32xzTYJP-O5Tdb4n_RJA",
      UNSPLASH_SECRET_KEY: "BkRu8j7j3bq3erI8xBAYTrAKR59hPwnR3-oWV6q2Q4I",
      DENKER_DEV_MODE: 'false', // Explicitly set for production
      DENKER_COORDINATOR_TIMEOUT_SECONDS: '120', // Set coordinator timeout to 2 minutes (120 seconds)
      DENKER_MEMORY_DATA_PATH: path.join(require('os').homedir(), 'Library', 'Application Support', 'denker-app', 'memory_data'), // Writable memory data path
      DENKER_SKIP_MEMORY_HEALTH_CHECK: 'true' // Skip memory health check for faster startup
    };
    // console.log(`[electron.js] Spawning local-backend with DENKER_DEFAULT_MCP_FS_ROOT=${defaultMcpFsRoot} and DENKER_USER_SETTINGS_PATH=${userSettingsFilePath}`);
    // Enhanced logging for all critical env vars being passed
    console.log(
      `[electron.js] Spawning local-backend with ENV (production: ${!isDev}): ` +
      `DENKER_USER_SETTINGS_PATH=${backendEnv.DENKER_USER_SETTINGS_PATH}, ` +
      `VITE_API_URL=${backendEnv.VITE_API_URL}, ` +
      `AUTH0_DOMAIN=${backendEnv.AUTH0_DOMAIN}, ` +
      `AUTH0_API_AUDIENCE=${backendEnv.AUTH0_API_AUDIENCE}, ` +
      `AUTH0_CLIENT_ID=${backendEnv.AUTH0_CLIENT_ID ? backendEnv.AUTH0_CLIENT_ID.substring(0,5) + '...' : 'MISSING'}, ` +
      `VERTEX_AI_PROJECT_ID=${backendEnv.VERTEX_AI_PROJECT_ID}, `+
      `VERTEX_AI_LOCATION=${backendEnv.VERTEX_AI_LOCATION}, `+
      `NODE_ENV=${backendEnv.NODE_ENV}, ` +
      `QDRANT_URL=${backendEnv.QDRANT_URL}, ` +
      `QDRANT_COLLECTION_NAME=${backendEnv.QDRANT_COLLECTION_NAME}, ` +
      `EMBEDDING_MODEL=${backendEnv.EMBEDDING_MODEL}, ` +
      `VECTOR_NAME=${backendEnv.VECTOR_NAME}, ` +
      `DENKER_DEV_MODE=${backendEnv.DENKER_DEV_MODE}, ` +
      `DENKER_MEMORY_DATA_PATH=${backendEnv.DENKER_MEMORY_DATA_PATH}, ` +
      `DENKER_SKIP_MEMORY_HEALTH_CHECK=${backendEnv.DENKER_SKIP_MEMORY_HEALTH_CHECK}, ` +
      `UNSPLASH_ACCESS_KEY=${backendEnv.UNSPLASH_ACCESS_KEY ? backendEnv.UNSPLASH_ACCESS_KEY.substring(0,8) + '...' : 'MISSING'}, ` +
      `PATH=${backendEnv.PATH}`
    );

    console.log(`[electron.js] Attempting to free port 9001 before starting local backend...`);
    freePort(9001, () => {
      console.log(`[electron.js] Port 9001 free-up attempt complete. Spawning local-backend-pkg...`);
      
      // Store the process globally for cleanup
      // Use 'pipe' instead of 'inherit' to avoid broken pipe issues in GUI app
      // Set working directory to a writable location so relative paths work
      const memoryDataDir = path.join(require('os').homedir(), 'Library', 'Application Support', 'denker-app');
      // Ensure the directory exists
      if (!fs.existsSync(memoryDataDir)) {
        fs.mkdirSync(memoryDataDir, { recursive: true });
      }
      
      backendProc = spawn(backendPath, [], { 
        stdio: ['ignore', 'pipe', 'pipe'], // stdin: ignore, stdout: pipe, stderr: pipe
        env: backendEnv,
        cwd: memoryDataDir // Set working directory to writable location
      });
      
      // Handle backend stdout/stderr
      if (backendProc.stdout) {
        backendProc.stdout.on('data', (data) => {
          console.log(`[BACKEND] stdout: ${data.toString()}`);
        });
      }
      
      if (backendProc.stderr) {
        backendProc.stderr.on('data', (data) => {
          console.log(`[BACKEND] stderr: ${data.toString()}`);
        });
      }
      
      backendProc.on('error', (spawnError) => {
        console.error(`[electron.js] Failed to start local-backend-pkg: ${spawnError.message}`);
        dialog.showErrorBox('Backend Error', `Failed to start the local backend process: ${spawnError.message}. Please ensure no other instances are running and try restarting the app.`);
        backendProc = null; // Clear reference on error
        
        // Notify frontend of backend failure
        if (mainWindow && mainWindow.webContents && !mainWindow.isDestroyed()) {
          mainWindow.webContents.send('backend-failed', `Backend process failed to start: ${spawnError.message}`);
        }
      });
      
      backendProc.on('close', (code) => {
        console.log(`local-backend-pkg (PyInstaller) exited with code ${code}`);
        backendProc = null; // Clear reference when process exits
        isBackendReady = false; // Mark backend as not ready
        
        // Notify frontend that backend stopped
        if (mainWindow && mainWindow.webContents && !mainWindow.isDestroyed()) {
          mainWindow.webContents.send('backend-stopped', `Backend process exited with code ${code}`);
        }
      });
      
      // Store PID for debugging
      if (backendProc && backendProc.pid) {
        console.log(`[electron.js] Local backend started with PID: ${backendProc.pid}`);
        
        // Start health checking after a brief delay to let the process initialize
        setTimeout(() => {
          checkBackendHealth();
        }, 2000); // Reduced from 5 seconds to 2 seconds since backend startup is optimized
      }
    });
  } else {
    // In development mode, assume backend is managed separately
    // Still check if it's ready for consistency
    setTimeout(() => {
      checkBackendHealth();
    }, 1000); // Shorter delay in dev mode
  }

  // --- ADD IPC Handlers for Auth --- 
  console.log('[*] Registering Auth IPC Handlers...');
  
  // Handler for renderer to request access token
  // MOVED to setupAuth0Authentication
    
  // --- ADDED: Handler for renderer to request user info --- 
  // MOVED to setupAuth0Authentication
  
  // Handler for renderer to initiate logout
  // MOVED to setupAuth0Authentication
  
  // Remove potentially conflicting old handlers if they exist
  console.log('[*] Cleaning up old IPC Handlers...');
  ipcMain.removeHandler('send-redirect-callback'); 
  ipcMain.removeHandler('handle-auth0-callback'); 
  // Add any others you might have used previously
  console.log('[*] IPC Handler setup complete.');
  // --- END Auth IPC Handlers ---

  // IPC handler to provide environment variables to the renderer
  // MOVED EARLIER, BEFORE createWindow call

  app.on('activate', function () {
    console.log('🚀 electron.js: app.on(\'activate\') triggered. Timestamp:', Date.now());
    if (BrowserWindow.getAllWindows().length === 0) createMainWindow();
  });
});

// Create a single, robust shutdown handler
const cleanupAndQuit = () => {
  console.log('🧹 Cleaning up before quit...');
  
  // Stop background token refresh
  stopBackgroundTokenRefresh();
  
  // Kill backend process if it exists
  if (backendProc) {
    console.log('Terminating backend process...');
    backendProc.kill('SIGTERM');
    backendProc = null;
  }
  
  // Unregister global shortcuts
  globalShortcut.unregisterAll();
  
  // Quit the app
  app.quit();
};

// --- Centralized Shutdown Logic ---
// `before-quit` is a fallback event for cleanup if cleanupAndQuit() wasn't called directly
app.on('before-quit', (event) => {
  console.log('[LIFECYCLE] before-quit event triggered.');
  
  // Only prevent and cleanup if we haven't already started the cleanup process
  if (!app.isQuitting) {
    event.preventDefault(); // Prevent default quit behavior to run our logic
    cleanupAndQuit();
  } else {
    console.log('[LIFECYCLE] Cleanup already in progress, allowing quit to proceed.');
  }
});

// On macOS, it's common for apps to stay open when windows are closed.
// We will explicitly quit using our consolidated method.
app.on('window-all-closed', () => {
  console.log('[LIFECYCLE] All windows closed. Quitting app.');
  cleanupAndQuit();
});

// Add IPC handler for Auth0 redirect callback
ipcMain.handle('send-redirect-callback', (event, appState) => {
  console.log('🔐 Received Auth0 redirect callback in main process:', appState);
  
  // Attempt to show main window if it exists
  if (mainWindow) {
    mainWindow.show();
    mainWindow.focus();
    
    // Send event to renderer to handle navigation
    mainWindow.webContents.send('auth0-callback', '/callback');
  } else {
    console.warn('❌ Main window not available during redirect callback');
    // Potentially recreate main window if needed
    createMainWindow();
  }
});

// Handle protocol URL (macOS)
app.on('open-url', (event, url) => {
  event.preventDefault();
  console.log('🔗 Protocol URL detected on macOS:', url);

  // Keep generic deep link handling if needed for other purposes
  if (mainWindow && mainWindow.webContents) {
     console.log('🔗 Forwarding deeplink URL to renderer (macOS):', url);
     mainWindow.webContents.send('deeplink-url', url);
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
      mainWindow.show();
  } else {
    console.warn('⚠️ mainWindow not available for protocol URL (macOS):', url);
     // Optionally store the URL if the window might be created later
     // deeplinkingUrl = url; 
  }
});

// Windows deep linking handler
app.on('second-instance', (event, commandLine, workingDirectory) => {
  console.log('🔄 Second instance detected with args (Windows):', commandLine);
  if (mainWindow) {
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.focus();
    mainWindow.show();

    // Check for denker:// protocol URLs (legacy support)
    const deepLinkUrl = commandLine.find(arg => arg.startsWith('denker://'));
    if (deepLinkUrl) {
      console.log('⚠️ Received deprecated custom protocol URL (Windows):', deepLinkUrl);
      
      // For any 'denker://' URLs, inform the user that we're now using HTTP
      if (deepLinkUrl.includes('callback')) {
        console.log('🔑 Auth0 callback via custom protocol detected - using HTTP server instead');
        const message = 'Auth0 now uses HTTP for callbacks. Please update your Auth0 settings to use http://localhost:8123/callback';
        mainWindow.webContents.executeJavaScript(
          `console.warn("${message}"); alert("${message}");`
        ).catch(console.error);
      } else {
        console.log('🔗 Forwarding non-callback deeplink (Windows):', deepLinkUrl);
        mainWindow.webContents.send('deeplink-url', deepLinkUrl);
      }
    }
  }
});

// Helper to calculate window width
function calculateWindowWidth() {
  return Math.floor(screen.getPrimaryDisplay().workAreaSize.width * MAIN_WINDOW_WIDTH_RATIO);
}

// Setup clipboard monitor
function setupClipboardMonitor() {
  console.log('🔍 DENKER DEBUG: Setting up clipboard monitor');
  
  // Initial clipboard content
  lastClipboardText = clipboard.readText();
  
  // Update the timestamp
  lastClipboardChangeTime = Date.now();
  
  // Check clipboard every 500ms
  clipboardMonitorInterval = setInterval(() => {
    const currentContent = clipboard.readText();
    
    // If content changed, update the timestamp
    if (currentContent !== lastClipboardText) {
      console.log('🔍 DENKER DEBUG: Clipboard content changed');
      console.log(`Previous content: "${lastClipboardText?.substring(0, 50)}${lastClipboardText?.length > 50 ? '...' : ''}"`);
      console.log(`New content: "${currentContent?.substring(0, 50)}${currentContent?.length > 50 ? '...' : ''}"`);
      lastClipboardText = currentContent;
      lastClipboardChangeTime = Date.now();
    }
  }, 500);
}

// Register global shortcut (Command+Shift+D)
function registerGlobalShortcut() {
  try {
    console.log('🔑 Attempting to register global shortcut: CommandOrControl+Shift+D');
    
    // Check if shortcut is already registered
    const isRegistered = globalShortcut.isRegistered('CommandOrControl+Shift+D');
    if (isRegistered) {
      console.warn('⚠️ Global shortcut CommandOrControl+Shift+D is already registered! Unregistering first...');
      globalShortcut.unregister('CommandOrControl+Shift+D');
    }
    
    const success = globalShortcut.register('CommandOrControl+Shift+D', async () => {
      console.log('🎯 Global shortcut triggered');
      try {
      // Get clipboard text
      const clipboardText = clipboard.readText();
      const clipboardAge = Date.now() - lastClipboardChangeTime;
      const isClipboardFresh = clipboardAge <= MAX_CLIPBOARD_AGE;
      
      console.log('📋 Clipboard info:', {
        text: clipboardText.substring(0, 100) + '...',
        age: clipboardAge,
        isFresh: isClipboardFresh,
        maxAge: MAX_CLIPBOARD_AGE
      });

      // Capture screenshot
      let screenshot = null;
      try {
        console.log('📸 Capturing screenshot...');
        
        // Check for macOS screen recording permissions
        if (process.platform === 'darwin') {
          const hasPermission = systemPreferences.getMediaAccessStatus('screen');
          console.log('🔐 macOS screen recording permission status:', hasPermission);
          
          // Debug app identity information
          console.log('🔍 App identity debug:', {
            appPath: app.getAppPath(),
            executablePath: process.execPath,
            bundleId: 'com.denker.app',  // Use correct bundle ID from Info.plist
            appGetName: app.getName(),   // Show what getName() returns for comparison
            version: app.getVersion(),
            isPackaged: app.isPackaged
          });
          
          // Track whether native dialog appeared
          let nativeDialogAppeared = false;
          
          // Always try to trigger permission dialog to register app properly
          console.log('🔄 Triggering permission request to register app with macOS...');
          try {
            // Force a WINDOW capture attempt to trigger permission registration
            // Note: We want window capture, not full screen capture
            const sources = await desktopCapturer.getSources({
              types: ['window'],  // Only windows, not full screen
              thumbnailSize: { width: 10, height: 10 }
            });
            console.log('✅ Window capture permission request triggered, got', sources.length, 'window sources');
            
            // Check permission again after trigger
            const newPermission = systemPreferences.getMediaAccessStatus('screen');
            console.log('🔍 Permission after trigger:', newPermission);
            
            // Detect if native dialog appeared by checking permission state changes
            // If permission went from 'not-determined' to 'denied' or 'granted', native dialog appeared
            if (hasPermission === 'not-determined' && 
                (newPermission === 'denied' || newPermission === 'granted')) {
              nativeDialogAppeared = true;
              console.log('🎯 Native macOS permission dialog appeared and user responded');
            }
            // If permission was already denied and we triggered but it's still denied,
            // native dialog likely didn't appear (already decided)
            else if (hasPermission === 'denied' && newPermission === 'denied') {
              nativeDialogAppeared = false;
              console.log('🚫 Native dialog did not appear (permission previously denied)');
            }
            // If permission was granted before, no dialog needed
            else if (hasPermission === 'granted') {
              nativeDialogAppeared = false; // No dialog needed
              console.log('✅ Permission already granted, no dialog needed');
            }
            // If permission is still 'not-determined' after trigger, dialog might be showing
            else if (hasPermission === 'not-determined' && newPermission === 'not-determined') {
              // Wait a moment to see if user responds to native dialog
              console.log('⏳ Permission still undetermined, waiting for potential native dialog response...');
              await new Promise(resolve => setTimeout(resolve, 1000)); // Wait 1 second
              
              const delayedPermission = systemPreferences.getMediaAccessStatus('screen');
              console.log('🔍 Permission after delay:', delayedPermission);
              
              if (delayedPermission !== 'not-determined') {
                nativeDialogAppeared = true;
                console.log('🎯 Native dialog appeared and user responded during delay');
              } else {
                nativeDialogAppeared = false;
                console.log('⚠️ Native dialog may not have appeared or user hasn\'t responded yet');
              }
            }
            
          } catch (forceError) {
            console.log('⚠️ Permission request trigger failed:', forceError.message);
            nativeDialogAppeared = false;
          }
          
          // Check final permission status
          const finalPermission = systemPreferences.getMediaAccessStatus('screen');
          console.log('🔐 Final permission status:', finalPermission);
          
          // Only show custom dialog if:
          // 1. Permission is not granted AND
          // 2. Native dialog did not appear (fallback case)
          if (finalPermission !== 'granted' && !nativeDialogAppeared) {
            console.warn('❌ Screen recording permission not granted and no native dialog appeared. Showing custom dialog as fallback.');
            
            // Show helpful dialog as fallback when native dialog doesn't appear
            const result = await dialog.showMessageBox({
              type: 'warning',
              title: 'Screen Recording Permission Required',
              message: 'Denker needs Screen Recording permission to capture screenshots.',
              detail: 'Bundle ID: com.denker.app\nExecutable: /Applications/Denker.app/Contents/MacOS/Denker\n\nTo enable screenshots:\n\n1. Go to System Preferences > Privacy & Security\n2. Click on Screen Recording\n3. REMOVE any existing Denker entries\n4. Enable Denker (should auto-appear after this trigger)\n5. Restart Denker\n\nFor now, Denker will work with text-only mode.',
              buttons: ['Continue Text-Only', 'Open System Preferences', 'Reset Permissions'],
              defaultId: 0,
              cancelId: 0
            });
            
            if (result.response === 1) {
              // Try multiple methods to open System Preferences
              console.log('🔧 Attempting to open System Preferences...');
              
              try {
                // Method 1: Try the new System Settings app (macOS 13+)
                await shell.openExternal('x-apple.systempreferences:com.apple.settings.PrivacySecurity.extension');
              } catch (error1) {
                console.warn('⚠️ Method 1 failed:', error1.message);
                
                try {
                  // Method 2: Try the old System Preferences URL
                  await shell.openExternal('x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture');
                } catch (error2) {
                  console.warn('⚠️ Method 2 failed:', error2.message);
                  
                  try {
                    // Method 3: Open System Preferences directly (user navigates manually)
                    await shell.openExternal('x-apple.systempreferences:');
                  } catch (error3) {
                    console.warn('⚠️ Method 3 failed:', error3.message);
                    
                    try {
                      // Method 4: Fallback to opening via command line
                      const { spawn } = require('child_process');
                      spawn('open', ['-b', 'com.apple.systempreferences']);
                      console.log('✅ Opened System Preferences via command line');
                    } catch (error4) {
                      console.error('❌ All methods failed:', error4.message);
                      dialog.showErrorBox(
                        'Cannot Open Settings', 
                        'Please manually go to:\nSystem Preferences → Privacy & Security → Screen Recording\n\nThen enable Denker and restart the app.'
                      );
                    }
                  }
                }
              }
            } else if (result.response === 2) {
              // Reset Permissions - nuclear option
              console.log('💥 User requested permission reset');
              
              try {
                const { spawn } = require('child_process');
                
                // Try to reset only Denker's permission (macOS 10.15+)
                const bundleId = 'com.denker.app';  // Correct bundle ID from Info.plist
                console.log(`🎯 Attempting to reset permission for bundle ID: ${bundleId}`);
                
                const resetResult = await new Promise((resolve, reject) => {
                  // Try specific app reset first (works on newer macOS versions)
                  const process = spawn('tccutil', ['reset', 'ScreenCapture', bundleId], {
                    stdio: ['pipe', 'pipe', 'pipe']
                  });
                  
                  let output = '';
                  process.stdout.on('data', (data) => output += data.toString());
                  process.stderr.on('data', (data) => data.toString());
                  
                  process.on('close', (code) => {
                    if (code === 0) {
                      resolve({ success: true, output, method: 'specific' });
                    } else {
                      console.warn(`⚠️ Specific reset failed (code ${code}), trying alternative method...`);
                      
                      // Fallback: Try removing via sqlite (more targeted)
                      const sqlProcess = spawn('sqlite3', [
                        '/Library/Application Support/com.apple.TCC/TCC.db',
                        `DELETE FROM access WHERE service='kTCCServiceScreenCapture' AND client='${bundleId}';`
                      ], { stdio: ['pipe', 'pipe', 'pipe'] });
                      
                      let sqlOutput = '';
                      sqlProcess.stdout.on('data', (data) => sqlOutput += data.toString());
                      sqlProcess.stderr.on('data', (data) => sqlOutput += data.toString());
                      
                      sqlProcess.on('close', (sqlCode) => {
                        if (sqlCode === 0) {
                          resolve({ success: true, output: sqlOutput, method: 'sqlite' });
                        } else {
                          reject(new Error(`Both methods failed. tccutil code: ${code}, sqlite code: ${sqlCode}`));
                        }
                      });
                    }
                  });
                });
                
                console.log(`✅ Denker permission reset successfully using ${resetResult.method} method`);
                dialog.showMessageBox({
                  type: 'info',
                  title: 'Denker Permissions Reset',
                  message: 'Screen recording permission has been reset for Denker only.',
                  detail: 'Other apps are not affected. Please restart Denker to grant permission again.'
                });
                
              } catch (resetError) {
                console.error('❌ Permission reset failed:', resetError.message);
                dialog.showErrorBox(
                  'Reset Failed',
                  `Could not reset permissions: ${resetError.message}\n\nPlease manually remove Denker from Screen Recording settings and try again.`
                );
              }
            }
          } else if (finalPermission !== 'granted' && nativeDialogAppeared) {
            console.log('🎯 Native macOS permission dialog appeared. User will decide. Not showing custom dialog.');
          } else {
            console.log('✅ Screen recording permission already granted or handled by native dialog.');
          }
        }
        
        // Check permission but still try capture since API can be unreliable
        const permissionStatus = process.platform === 'darwin' ? systemPreferences.getMediaAccessStatus('screen') : 'granted';
        console.log('🔐 Permission status from API:', permissionStatus);
        
        if (permissionStatus === 'denied') {
          console.log('⚠️ API reports permission denied, but attempting capture anyway (API can be stale)');
        }
        
        // Always try capture - let the actual capture attempt determine success
        {
          // Try multiple thumbnail sizes for better compatibility
          const thumbnailSizes = [
            { width: 1280, height: 720 },   // HD resolution
            { width: 800, height: 600 },    // Smaller fallback
            { width: 400, height: 300 }     // Smallest fallback
          ];
          
          let sources = null;
          let usedSize = null;
          
          for (const size of thumbnailSizes) {
            try {
              console.log(`📸 Trying thumbnail size: ${size.width}x${size.height}`);
              sources = await desktopCapturer.getSources({
                types: ['window'],
                thumbnailSize: size,
                fetchWindowIcons: false
              });
              
              // Check if we got valid thumbnails
              const validSources = sources.filter(s => s.thumbnail && !s.thumbnail.isEmpty());
              if (validSources.length > 0) {
                console.log(`✅ Got ${validSources.length} valid thumbnails with size ${size.width}x${size.height}`);
                usedSize = size;
                break;
              } else {
                console.warn(`⚠️ All thumbnails empty with size ${size.width}x${size.height} - likely permission issue`);
              }
            } catch (error) {
              console.warn(`⚠️ Failed with size ${size.width}x${size.height}:`, error.message);
            }
          }
          
          if (!sources) {
            console.error('❌ Failed to capture with any thumbnail size - check screen recording permissions');
            screenshot = null;
          } else {
            console.log('📸 Available windows:', sources.map(s => s.name));

        // Filter out Denker windows and system windows
        const filteredSources = sources.filter(source => {
          const name = source.name.toLowerCase();
          return !name.includes('denker') 
        });

            if (filteredSources.length > 0) {
              // Get the most recently active window
              const activeWindow = filteredSources[0];
              console.log('📸 Selected window:', activeWindow.name);
              
              // Check if thumbnail exists and has size
              console.log('📸 Thumbnail info:', {
                hasThumbnail: !!activeWindow.thumbnail,
                thumbnailSize: activeWindow.thumbnail ? {
                  width: activeWindow.thumbnail.getSize().width,
                  height: activeWindow.thumbnail.getSize().height
                } : null,
                isEmpty: activeWindow.thumbnail ? activeWindow.thumbnail.isEmpty() : true
              });
              
              if (activeWindow.thumbnail && !activeWindow.thumbnail.isEmpty()) {
                screenshot = activeWindow.thumbnail.toDataURL();
                console.log('📸 Screenshot captured successfully:', {
                  hasScreenshot: !!screenshot,
                  screenshotType: typeof screenshot,
                  screenshotLength: screenshot?.length,
                  screenshotPreview: screenshot?.substring(0, 100) + '...',
                  dataUrlValid: screenshot?.includes('base64,') && screenshot?.length > 50
                });
              } else {
                console.log('❌ Thumbnail is empty or invalid');
                screenshot = null;
              }
            } else {
              console.log('⚠️ No suitable window found for capture');
              screenshot = null;
            }
          }
        }
      } catch (error) {
        console.error('❌ Screenshot capture error:', error);
      }

      // Determine mode based on available data and clipboard freshness
      const mode = isClipboardFresh 
        ? (screenshot ? 'both' : 'text')
        : (screenshot ? 'screenshot' : 'error');
      console.log('🎯 Mode determined:', mode);

      // Create capture data object
      const captureData = {
        text: clipboardText,
        screenshot: screenshot,
        mode: mode,
        timestamp: Date.now(),
        clipboardAge: clipboardAge,
        metadata: {
          captureTime: Date.now()
        }
      };
      console.log('📦 Capture data prepared:', {
        textLength: clipboardText.length,
        hasScreenshot: !!screenshot,
        mode: mode,
        clipboardAge: clipboardAge
      });

      // Create subwindow immediately with capture data
      console.log('🪟 Creating subwindow with capture data...');
      await createSubWindowWithData(captureData);
      console.log('✅ Subwindow created successfully');

      // Notify subwindow that API loading has started
      if (subWindow) {
        console.log('🔄 Notifying subwindow that API loading has started');
        subWindow.webContents.send('api-loading', true);
      }

      // Call intention agent API in background
      console.log('🌐 Calling intention agent API...');
      
      let screenshotData = null;
      let screenshotMimeType = null;

      console.log('🔍 Screenshot debugging:', {
        hasScreenshot: !!screenshot,
        screenshotType: typeof screenshot,
        screenshotLength: screenshot?.length,
        screenshotPreview: screenshot?.substring(0, 50) + '...'
      });

      if (screenshot) {
        console.log('🎯 Processing screenshot data URL...');
        // The screenshot is a data URL like "data:image/png;base64,iVBORw0K..."
        const parts = screenshot.match(/^data:(.*);base64,(.*)$/);
        console.log('🔍 Data URL parsing result:', {
          hasParts: !!parts,
          partsLength: parts?.length,
          mimeType: parts?.[1],
          base64DataLength: parts?.[2]?.length
        });
        
        if (parts && parts.length === 3) {
          screenshotMimeType = parts[1]; // e.g., "image/png"
          screenshotData = parts[2];     // The raw base64 data
          console.log('✅ Screenshot data extracted successfully:', {
            mimeType: screenshotMimeType,
            dataLength: screenshotData.length
          });
        } else {
          console.warn('⚠️ Failed to parse data URL, using fallback');
          // Fallback for safety, though it should be a data URL
          screenshotData = screenshot;
          screenshotMimeType = 'image/png'; // Assume PNG if format is unknown
        }
      } else {
        console.log('❌ No screenshot data available for API request');
      }

      const apiRequest = {
        query_id: `query_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`,
        text: clipboardText,
        screenshot: screenshotData,
        screenshot_mime_type: screenshotMimeType,
        mode: mode
      };

      // ADDED: Detailed logging before sending
      console.log('📦 Preparing to send API request:', {
        query_id: apiRequest.query_id,
        mode: apiRequest.mode,
        textLength: apiRequest.text?.length,
        hasScreenshot: !!apiRequest.screenshot,
        screenshotLength: apiRequest.screenshot?.length,
        screenshotMimeType: apiRequest.screenshot_mime_type
      });

      try {
        console.log('🔄 Starting API request...');
        const requestStartTime = Date.now();
        
        const response = await fetch(`${API_URL}/agents/intention`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(API_KEY ? { 'Authorization': `Bearer ${API_KEY}` } : {})
          },
          body: JSON.stringify(apiRequest),
          signal: AbortSignal.timeout(30000)
        });

        const responseTime = Date.now() - requestStartTime;
        console.log(`✅ Received response after ${responseTime}ms`);

        if (!response.ok) {
          throw new Error(`API call failed: ${response.status}`);
        }

        console.log('🔄 Parsing response JSON...');
        const parseStartTime = Date.now();
        const apiData = await response.json();
        const parseTime = Date.now() - parseStartTime;
        console.log(`✅ JSON parsing completed in ${parseTime}ms`);

        console.log('🌐 API response received:', {
          optionsCount: apiData.options?.length || 0,
          hasError: !!apiData.error,
          totalTime: Date.now() - requestStartTime
        });

        // Send API response to subwindow
        if (subWindow) {
          // Notify subwindow that API loading has finished
          console.log('🔄 Notifying subwindow that API loading has finished');
          subWindow.webContents.send('api-loading', false);
          // Send the API response
          subWindow.webContents.send('api-response', apiData);
        }

      } catch (error) {
        console.error('❌ API call error:', error);
        if (subWindow) {
          // Notify subwindow that API loading has finished with error
          console.log('🔄 Notifying subwindow that API loading has finished with error');
          subWindow.webContents.send('api-loading', false);
          // Send the error
          subWindow.webContents.send('api-error', error.message);
        }
      }

      } catch (error) {
        console.error('❌ Error in shortcut handler:', error);
        dialog.showErrorBox('Error', `Failed to process capture: ${error.message}`);
      }
    });

    if (success) {
      console.log('✅ Global shortcut CommandOrControl+Shift+D registered successfully!');
    } else {
      console.error('❌ Failed to register global shortcut CommandOrControl+Shift+D');
      console.log('🔍 Checking all currently registered shortcuts:');
      globalShortcut.getRegisteredAccelerators().forEach(shortcut => {
        console.log(`  - ${shortcut}`);
      });
    }
  } catch (error) {
    console.error('❌ Error registering global shortcut:', error);
    dialog.showErrorBox('Shortcut Registration Error', `Failed to register global shortcut: ${error.message}`);
  }
}

// Create or reuse subwindow with data
async function createSubWindowWithData(captureData) {
  try {
    console.log('🪟 Starting subwindow creation...');
    
    // If window exists, destroy it to create a fresh one
    if (subWindow) {
      subWindow.destroy();
      subWindow = null;
    }

    console.log('Creating new subwindow...');
    // Create new window
    subWindow = new BrowserWindow({
      width: SUB_WINDOW_WIDTH,
      height: SUB_WINDOW_HEIGHT,
      frame: false,
      transparent: true,
      webPreferences: {
        nodeIntegration: false,
        contextIsolation: true,
        preload: path.join(__dirname, 'preload.js'),
        devTools: true
      },
      alwaysOnTop: true,
      show: false,
      skipTaskbar: true,
      focusable: true,
      fullscreenable: false,
      hasShadow: true,
      resizable: false,
      minimizable: false,
      maximizable: false,
      closable: true
    });

    // Load the app with subwindow route
    const startUrl = isDev
      ? 'http://localhost:5173/#/subwindow'
      : `file://${path.join(__dirname, 'index.html#/subwindow')}`;
    
    console.log('Loading URL:', startUrl);
    
    // Wait for window to load and be ready
    await new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        reject(new Error('Timeout loading window'));
      }, 10000);

      let isLoaded = false;
      let isDomReady = false;

      const checkReady = () => {
        if (isLoaded && isDomReady) {
          clearTimeout(timeout);
          resolve();
        }
      };

      subWindow.webContents.once('did-finish-load', () => {
        console.log('Window finished loading');
        isLoaded = true;
        checkReady();
      });

      subWindow.webContents.once('dom-ready', () => {
        console.log('Window DOM ready');
        isDomReady = true;
        checkReady();
      });

      subWindow.webContents.once('did-fail-load', (event, errorCode, errorDescription) => {
        clearTimeout(timeout);
        reject(new Error(`Failed to load window: ${errorDescription}`));
      });

      subWindow.loadURL(startUrl);
    });

    // Add a small delay to ensure the preload script is fully initialized
    await new Promise(resolve => setTimeout(resolve, 100));

    // Send capture data and show window
    console.log('Window loaded, sending capture data...');
    subWindow.webContents.send('capture-data', captureData);
    
    // Position and show window
    positionSubWindowNearCursor();
    subWindow.setAlwaysOnTop(true, 'floating');
    subWindow.show();

    // Open DevTools in development mode
    if (isDev) {
      subWindow.webContents.openDevTools({ mode: 'detach' });
    }

    // Handle window close
    subWindow.on('closed', () => {
      subWindow = null;
    });

  } catch (error) {
    console.error('Error in createSubWindowWithData:', error);
    dialog.showErrorBox('Error', 'Failed to create window. Please try again.');
    if (subWindow) {
      subWindow.destroy();
      subWindow = null;
    }
  }
}

// Position the subwindow near the cursor
function positionSubWindowNearCursor() {
  if (!subWindow) return;

  // Get cursor position
  const cursor = screen.getCursorScreenPoint();
  
  // Get the display containing the cursor
  const display = screen.getDisplayNearestPoint(cursor);
  
  // Get window size
  const [width, height] = subWindow.getSize();
  
  // Calculate position to ensure window is fully visible
  let x = cursor.x;
  let y = cursor.y;
  
  // Adjust if window would go off screen
  if (x + width > display.bounds.x + display.bounds.width) {
    x = display.bounds.x + display.bounds.width - width;
  }
  if (y + height > display.bounds.y + display.bounds.height) {
    y = display.bounds.y + display.bounds.height - height;
  }
  
  // Set window position
  subWindow.setPosition(x, y);
}

// Create the browser window
function createMainWindow() {
  fs.appendFileSync(startupLogPath, `createMainWindow function STARTED at ${new Date().toISOString()}\n`);
  console.log('🚀 electron.js: createMainWindow() function STARTED. Timestamp:', Date.now());
  const preloadPath = path.join(__dirname, 'preload.js');
  console.log(' इलेक्ट्रॉन 🅿️ Preload script absolute path being used:', preloadPath);
  fs.appendFileSync(startupLogPath, `Preload path determined as: ${preloadPath} at ${new Date().toISOString()}\n`);

  mainWindow = new BrowserWindow({
    width: calculateWindowWidth(),
    height: screen.getPrimaryDisplay().workAreaSize.height,
    x: screen.getPrimaryDisplay().workAreaSize.width - calculateWindowWidth(),
    y: 0,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: preloadPath,
      additionalArguments: [
        `--api-url=${RENDERER_ENV_VARS.VITE_API_URL}`,
        `--ws-url=${RENDERER_ENV_VARS.VITE_WS_URL}`,
        `--auth0-domain=${RENDERER_ENV_VARS.VITE_AUTH0_DOMAIN || ''}`,
        `--auth0-client-id=${RENDERER_ENV_VARS.VITE_AUTH0_CLIENT_ID || ''}`,
        `--auth0-audience=${RENDERER_ENV_VARS.VITE_AUTH0_AUDIENCE || ''}`,
        `--node-env=${RENDERER_ENV_VARS.VITE_NODE_ENV || 'development'}`
      ]
    },
    frame: false,
    transparent: false, // Start with non-transparent window for login
    backgroundColor: '#121212', // Dark background when not transparent
    alwaysOnTop: true,
    skipTaskbar: true,
    hasShadow: true,
    resizable: true,
    minimizable: true,
    maximizable: false,
    closable: false // Disable system close button
  });

  // Load the app
  const startUrl = isDev
    ? 'http://localhost:5173/#/'
    : `file://${path.join(__dirname, 'index.html#/')}`;
  
  mainWindow.loadURL(startUrl);

  // Position window on the right side of the screen
  const { width, height } = screen.getPrimaryDisplay().workAreaSize;
  mainWindow.setPosition(
    Math.floor(width * (1 - MAIN_WINDOW_WIDTH_RATIO)),
    0
  );

  // Handle window close button click
  mainWindow.on('close', (event) => {
    console.log('MainWindow close event triggered. app.isQuitting =', app.isQuitting);
    
    // Only prevent close if not quitting the app
    if (!app.isQuitting) {
      console.log('Preventing close and hiding window instead');
      event.preventDefault();
      mainWindow.hide();
      return false;
    }
    
    console.log('Allowing window to close because app.isQuitting is true');
    // If we're quitting, make sure we destroy the window
    setTimeout(() => {
      if (mainWindow) {
        console.log('Destroying main window from close handler');
        mainWindow.destroy();
        mainWindow = null;
      }
    }, 0);
  });

  // Handle window minimize
  mainWindow.on('minimize', (event) => {
    event.preventDefault();
    mainWindow.hide();
  });

  // Handle window blur
  mainWindow.on('blur', () => {
    // Keep window on top even when not focused
    mainWindow.setAlwaysOnTop(true, 'floating');
  });

  // Handle window focus
  mainWindow.on('focus', () => {
    mainWindow.setAlwaysOnTop(true, 'floating');
  });

  // Handle window show
  mainWindow.on('show', () => {
    mainWindow.setAlwaysOnTop(true, 'floating');
  });

  // Handle window restore
  mainWindow.on('restore', () => {
    mainWindow.setAlwaysOnTop(true, 'floating');
  });
}







// IPC handlers
ipcMain.handle('minimize-main-window', () => {
  if (mainWindow) {
    mainWindow.minimize();
  }
});

ipcMain.handle('close-sub-window', () => {
  console.log('🪟 Close subwindow request received');
  
  try {
    if (subWindow) {
      console.log('🪟 Subwindow exists, attempting to close it');
      subWindow.destroy(); // Force destruction instead of normal close
      console.log('🪟 Subwindow destroyed');
      subWindow = null;
    } else {
      console.log('🪟 No subwindow to close');
    }
    return true;
  } catch (error) {
    console.error('❌ Error closing subwindow:', error);
    return false;
  }
});

ipcMain.handle('open-main-window', () => {
  if (mainWindow) {
    mainWindow.show();
  }
});

ipcMain.handle('get-selected-text', () => {
  const lastCapture = store.get('lastCapture', {});
  return lastCapture.text || '';
});

ipcMain.handle('capture-screenshot', () => {
  const lastCapture = store.get('lastCapture', {});
  return {
    data: lastCapture.screenshot || '',
    format: lastCapture.screenshotFormat || '',
    size: lastCapture.screenshotSize || 0
  };
});

ipcMain.handle('send-selected-option', async (event, option) => {
  try {
    console.log('🎯 Selected option received:', option);
    
    // Forward the selected option to main window
    if (mainWindow) {
      console.log('📤 Forwarding selected option to main window');
      mainWindow.webContents.send('selected-option', option);
    } else {
      console.error('❌ Main window not available to forward selected option');
      throw new Error('Main window not available');
    }

    return true;
  } catch (error) {
    console.error('❌ Error forwarding selected option:', error);
    throw error;
  }
});

// IPC handlers for API configuration
ipcMain.handle('get-api-url', () => {
  return API_URL;
});

ipcMain.handle('get-api-key', () => {
  return API_KEY;
});

// Add new IPC handler for toggling window transparency
ipcMain.handle('toggle-transparency', (event, isTransparent) => {
  if (mainWindow) {
    mainWindow.setBackgroundColor(isTransparent ? '#00000000' : '#121212');
    mainWindow.setOpacity(isTransparent ? 0.9 : 1.0);
    // Fix: setTransparent doesn't exist, use setVibrancy instead on macOS or simply set transparent property
    if (process.platform === 'darwin') {
      if (isTransparent) {
        mainWindow.setVibrancy('ultra-dark');
      } else {
        mainWindow.setVibrancy(null);
      }
    }
    return true;
  }
  return false;
});

// Create tray icon with context menu
function createTray() {
  // Skip tray creation completely
  console.log('Tray icon creation disabled');
  return;

  // Original code (now unreachable)
  const iconPath = path.join(__dirname, isDev ? './tray_icon.png' : './tray_icon.png');
  
  // Create smaller tray icon (16x16 for macOS)
  tray = new Tray(iconPath);
  
  // Set icon size for macOS - the icon should be properly sized in the file already
  // but we can adjust the context menu settings
  tray.setToolTip('Denker');
  
  const contextMenu = Menu.buildFromTemplate([
    { 
      label: 'Show Denker', 
      click: () => {
        if (mainWindow) {
          mainWindow.show();
        }
      } 
    },
    { type: 'separator' },
    { 
      label: 'Settings', 
      click: () => {
        if (mainWindow) {
          mainWindow.show();
          mainWindow.webContents.send('navigate', '/settings');
        }
      } 
    },
    { 
      label: 'About Denker', 
      click: () => {
        if (mainWindow) {
          mainWindow.show();
          mainWindow.webContents.send('navigate', '/about');
        }
      } 
    },
    { type: 'separator' },
    { 
      label: 'Quit',
      accelerator: 'CmdOrCtrl+Q',
      click: () => {
        console.log('Quit menu item clicked');
        cleanupAndQuit(); // Use the consolidated quit method
      } 
    }
  ]);
  
  tray.setContextMenu(contextMenu);
  
  // Show app when tray icon is clicked
  tray.on('click', () => {
    if (mainWindow) {
      mainWindow.show();
    }
  });
}

// Setup macOS app menu
function setupAppMenu() {
  // Create application menu
  const template = [
    // App menu (macOS only)
    ...(process.platform === 'darwin' ? [{
      label: app.name,
      submenu: [
        { role: 'about' },
        { type: 'separator' },
        // Add Settings submenu with Profile and Logout options
        {
          label: 'Settings',
          submenu: [
            {
              label: 'Profile',
              click: () => {
                // Send navigate event to the renderer
                if (mainWindow) {
                  mainWindow.webContents.send('navigate', '/profile');
                }
              }
            },
            {
              label: 'Logout',
              click: () => {
                // Send navigate event to trigger logout in renderer
                if (mainWindow) {
                  mainWindow.webContents.send('navigate', '/logout');
                }
              }
            }
          ]
        },
        { type: 'separator' },
        { role: 'services' },
        { type: 'separator' },
        { role: 'hide' },
        { role: 'hideOthers' },
        { role: 'unhide' },
        { type: 'separator' },
        { 
          label: 'Quit',
          accelerator: 'CmdOrCtrl+Q',
          click: () => {
            console.log('Quit menu item clicked');
            cleanupAndQuit(); // Use the consolidated quit method
          } 
        }
      ]
    }] : []),
    
    // File menu
    {
      label: 'File',
      submenu: [
        { role: 'close' }
      ]
    },
    
    // Edit menu
    {
      label: 'Edit',
      submenu: [
        { role: 'undo' },
        { role: 'redo' },
        { type: 'separator' },
        { role: 'cut' },
        { role: 'copy' },
        { role: 'paste' },
        ...(process.platform === 'darwin' ? [
          { role: 'pasteAndMatchStyle' },
          { role: 'delete' },
          { role: 'selectAll' },
          { type: 'separator' },
          {
            label: 'Speech',
            submenu: [
              { role: 'startSpeaking' },
              { role: 'stopSpeaking' }
            ]
          }
        ] : [
          { role: 'delete' },
          { type: 'separator' },
          { role: 'selectAll' }
        ])
      ]
    },
    
    // View menu
    {
      label: 'View',
      submenu: [
        { role: 'reload' },
        { role: 'forceReload' },
        { role: 'toggleDevTools' },
        { type: 'separator' },
        { role: 'resetZoom' },
        { role: 'zoomIn' },
        { role: 'zoomOut' },
        { type: 'separator' },
        { role: 'togglefullscreen' }
      ]
    },
    
    // Window menu
    {
      label: 'Window',
      submenu: [
        { role: 'minimize' },
        { role: 'zoom' },
        ...(process.platform === 'darwin' ? [
          { type: 'separator' },
          { role: 'front' },
          { type: 'separator' },
          { role: 'window' }
        ] : [
          { role: 'close' }
        ])
      ]
    },
    
    // Help menu
    {
      label: 'Help',
      submenu: [
        {
          label: 'Getting Started',
          click: () => {
            // Send navigate event to the renderer to show onboarding
            if (mainWindow) {
              mainWindow.webContents.send('show-onboarding');
            }
          }
        },
        {
          label: 'Feedback',
          click: () => {
            // Send navigate event to the renderer
            if (mainWindow) {
              mainWindow.webContents.send('navigate', '/feedback');
            }
          }
        },
        {
          label: 'Learn More',
          click: async () => {
            const { shell } = require('electron');
            await shell.openExternal('https://denker.ai');
  }
        }
      ]
    }
  ];
  
  const menu = Menu.buildFromTemplate(template);
  Menu.setApplicationMenu(menu);
} 

// Global variable to track whether authentication is in progress
let authenticationInProgress = false;

/**
 * Starts the Auth0 callback HTTP server in production mode
 * Following Auth0 best practices for desktop applications
 */
function startAuthServer() {
  if (authServer) {
    console.log('⚠️ Auth server already running');
    return;
  }
  
  console.log('🔒 Starting Auth0 callback server for production mode');
  
  // Create the auth server
  authServer = createAuthServer({
    port: 8123,
    onCallback: handleAuth0Callback
  });
  
  // Handle server errors
  authServer.on('error', (err) => {
    console.error('❌ Auth server error:', err);
    authServer = null;
  });
}

/**
 * Handle Auth0 callback data received from the local HTTP server
 * Following best practices for Electron Auth0 integration
 */
function handleAuth0Callback(params) {
  console.log('🔑 Auth0 callback received from system browser:', { 
    hasCode: !!params.code,
    hasState: !!params.state,
  });
  
  // Verify Auth0 state parameter (keep this active)
  if (global.auth0State && params.state !== global.auth0State) {
    console.error('⚠️ Auth0 state mismatch - potential CSRF attack. Aborting callback processing.');
    if (mainWindow && mainWindow.webContents) {
      mainWindow.webContents.send('auth0-login-error', 'State mismatch error. Please try logging in again.');
    }
    return; // Stop processing if state doesn't match
  }
  
  // Clear used state
  global.auth0State = null;
  console.log('✅ Main process state validation passed.');
  
  ensureMainWindow(() => {
    if (!mainWindow || !mainWindow.webContents || mainWindow.isDestroyed()) {
      console.error('❌ Cannot send auth callback data - no valid main window available');
      return;
    }

    // Instead of navigating with loadURL, send code/state via IPC
    console.log('[AUTH_DEBUG] electron.js: Sending auth0-callback-data IPC to renderer.');
    mainWindow.webContents.send('auth0-callback-data', { 
      code: params.code, 
      state: params.state 
    });

    // Focus the window after sending IPC
    focusMainWindow(); 
  });
}

/**
 * Make sure the main window exists and is ready
 * Enhanced to handle various window states more reliably
 */
function ensureMainWindow(callback) {
  // Check for all possible window states
  if (!mainWindow || mainWindow.isDestroyed()) {
    console.log('📢 Creating new main window for auth callback');
    // Pass the callback to createMainWindow if it supports it,
    // otherwise, rely on app.whenReady or similar event
    createMainWindow(() => { // Assuming createMainWindow can take a callback or sets up listeners
       setTimeout(() => { // Add delay to ensure window is fully ready
         if (mainWindow && !mainWindow.isDestroyed()) {
            focusMainWindow();
            callback();
         } else {
            console.error("Failed to create/ensure main window for callback.")
         }
       }, 1000); // Adjust delay if needed
    });

  } else {
     // Window exists, ensure it's visible and focused
     console.log('📢 Main window exists, ensuring visibility for auth callback');
     focusMainWindow(); // Use existing focus logic

     // Execute the callback after a short delay, only if it's a valid function
     if (typeof callback === 'function') {
        setTimeout(callback, 200);
     } else {
        console.warn('[ensureMainWindow] No valid callback provided to execute after focusing window.')
     }
  }
}

/**
 * Focuses the main window and brings it to the front.
 */
function focusMainWindow() {
    if (mainWindow && !mainWindow.isDestroyed()) {
        console.log('✨ Focusing main window');
        if (mainWindow.isMinimized()) {
            mainWindow.restore();
        }
        mainWindow.show(); // Ensure it's visible
        mainWindow.focus(); // Focus the window
        
        // Optional: Bring to front with always-on-top temporarily
        mainWindow.setAlwaysOnTop(true);
        setTimeout(() => {
          if (mainWindow && !mainWindow.isDestroyed()) mainWindow.setAlwaysOnTop(false);
        }, 1000);
        
        // For macOS, bring app to foreground
        if (process.platform === 'darwin') {
          app.show();
          app.focus({ steal: true }); // steal focus if needed
        }
    } else {
        console.warn('⚠️ Tried to focus main window, but it doesn\'t exist or is destroyed.');
    }
}

// ... existing code ...

function forwardAuthDataToRenderer(params) { // This function seems unused or part of an old flow, consider removing if confirm unused.
  console.log('📡 Forwarding auth data to renderer:', params);

  if (mainWindow && mainWindow.webContents) {
    // Ensure main window is visible and focused
  mainWindow.show();
  mainWindow.focus();
    
    // Send the Auth0 parameters to the renderer
    mainWindow.webContents.send('auth0-params', params);
  } else {
    console.error('❌ Cannot forward auth data - main window not available');
  }
}

// Key for storing auth tokens in electron-store
const AUTH_TOKEN_KEY = 'authTokens';

// Background token refresh system
let tokenRefreshInterval = null;
let isRefreshingToken = false;

// Helper function to check if token needs refresh (15 minutes before expiry)
function shouldRefreshToken(tokenData) {
  if (!tokenData || !tokenData.accessToken || !tokenData.refreshToken) {
    return false;
  }
  
  const bufferSeconds = 15 * 60; // 15 minutes buffer
  const expiresAt = tokenData.receivedAt + (tokenData.expiresIn * 1000) - (bufferSeconds * 1000);
  return Date.now() > expiresAt;
}

// Background token refresh function
async function performBackgroundTokenRefresh() {
  if (isRefreshingToken) {
    console.log('[Background Refresh] Token refresh already in progress, skipping');
    return;
  }
  
  const tokenData = store.get(AUTH_TOKEN_KEY);
  if (!shouldRefreshToken(tokenData)) {
    return; // No refresh needed
  }
  
  console.log('[Background Refresh] Starting proactive token refresh');
  isRefreshingToken = true;
  
  try {
    const auth0Domain = RENDERER_ENV_VARS.VITE_AUTH0_DOMAIN;
    const clientId = RENDERER_ENV_VARS.VITE_AUTH0_CLIENT_ID;
    const tokenUrl = `https://${auth0Domain}/oauth/token`;

    const refreshParams = new URLSearchParams({
      grant_type: 'refresh_token',
      client_id: clientId,
      refresh_token: tokenData.refreshToken,
    });

    console.log('[Background Refresh] Requesting new token from Auth0');
    const response = await fetch(tokenUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: refreshParams,
    });

    const newTokens = await response.json();

    if (!response.ok) {
      console.error('[Background Refresh] Token refresh failed:', newTokens);
      // Don't clear tokens on background refresh failure - let the user-initiated refresh handle it
      return;
    }

    console.log('[Background Refresh] Token refresh successful');
    const newTokenData = {
      accessToken: newTokens.access_token,
      idToken: newTokens.id_token,
      refreshToken: newTokens.refresh_token || tokenData.refreshToken,
      expiresIn: newTokens.expires_in,
      scope: newTokens.scope || tokenData.scope,
      receivedAt: Date.now(),
    };
    
    store.set(AUTH_TOKEN_KEY, newTokenData);
    console.log('[Background Refresh] New tokens stored successfully');
    
    // Notify renderer of successful background refresh
    if (mainWindow && mainWindow.webContents && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('token-refreshed', { success: true });
    }
    
  } catch (error) {
    console.error('[Background Refresh] Error during background token refresh:', error);
    // Don't clear tokens on background refresh error
  } finally {
    isRefreshingToken = false;
  }
}

// Start background token refresh timer
function startBackgroundTokenRefresh() {
  if (tokenRefreshInterval) {
    clearInterval(tokenRefreshInterval);
  }
  
  // Check every 5 minutes
  tokenRefreshInterval = setInterval(performBackgroundTokenRefresh, 5 * 60 * 1000);
  console.log('[Background Refresh] Background token refresh timer started (5 minute intervals)');
}

// Stop background token refresh timer
function stopBackgroundTokenRefresh() {
  if (tokenRefreshInterval) {
    clearInterval(tokenRefreshInterval);
    tokenRefreshInterval = null;
    console.log('[Background Refresh] Background token refresh timer stopped');
  }
}

// Define setupAuth0Authentication function
function setupAuth0Authentication() {
  console.log('🔐 Setting up Auth0 authentication listeners...');
  
  // Start the HTTP callback server ONLY IN PRODUCTION
  // In Dev, Vite's server or direct redirects might be used
  if (!isDev) { // Assuming 'isDev' is defined in this scope
    console.log("[AUTH Setup] Starting HTTP callback server for Production.");
    startAuthServer(); 
  } else {
    console.log("[AUTH Setup] Skipping HTTP callback server start in Development.");
    // In Dev mode, set up an IPC handler for the renderer to send auth params
    ipcMain.handle('dev-process-auth0-callback', async (event, params) => {
      console.log('[MAIN_PROCESS_DEV_AUTH] Received code and state from renderer:', { hasCode: !!params.code, hasState: !!params.state });
      try {
        // Directly call the main handler used by the production auth server
        // This reuses all existing logic for token exchange, state validation, IPC back to renderer etc.
        await handleAuth0Callback(params); // handleAuth0Callback is already async
        // handleAuth0Callback itself will send 'auth-successful' or 'auth-failed' to the renderer.
        return { success: true }; // Indicates IPC call was received and initiated processing
      } catch (error) {
        console.error('[MAIN_PROCESS_DEV_AUTH] Critical error during handleAuth0Callback invocation in dev:', error);
        // This catch is for errors in *calling* handleAuth0Callback or if it throws unexpectedly
        // handleAuth0Callback should ideally handle its own errors and send 'auth-failed'.
        // If handleAuth0Callback fails to send 'auth-failed', we send a generic one.
        if (event.sender && !event.sender.isDestroyed()) {
            event.sender.send('auth-failed', { error: 'dev_callback_processing_error', error_description: error.message || 'Unknown error processing dev callback.' });
        }
        return { success: false, error: error.message || 'Unknown error processing dev callback.' };
      }
    });
    console.log('[MAIN_PROCESS_DEV_AUTH] IPC handler "dev-process-auth0-callback" is ready for development mode.');
  }
  
  // Register IPC listener for renderer to trigger system browser login
  ipcMain.handle('login', async () => {
    console.log('🔓 Received login request from renderer');
    try {
      openSystemBrowserForAuth(); 
      return { success: true }; 
    } catch (error) {
       console.error("❌ Error initiating login:", error);
       return { success: false, error: error.message || 'Failed to start login process.' };
    }
  });
  console.log("🔐 Auth0 login request listener ('login') ready.");

  // IPC Handler for getting the access token
  ipcMain.handle('get-access-token', async () => {
    console.log('[IPC] Handling get-access-token');
    const tokenData = store.get(AUTH_TOKEN_KEY);

    if (!tokenData || !tokenData.accessToken) {
      console.log('[IPC] No access token data found in store.');
      return null;
    }

    // Check for token expiration (with a 60-second buffer for immediate use)
    const bufferSeconds = 60;
    const expiresAt = tokenData.receivedAt + (tokenData.expiresIn * 1000) - (bufferSeconds * 1000);
    const isTokenExpired = Date.now() > expiresAt;

    if (isTokenExpired) {
      console.log('[IPC] Access token expired or nearing expiration. Attempting immediate refresh.');
      if (tokenData.refreshToken) {
        try {
          const auth0Domain = RENDERER_ENV_VARS.VITE_AUTH0_DOMAIN;
          const clientId = RENDERER_ENV_VARS.VITE_AUTH0_CLIENT_ID;
          const tokenUrl = `https://${auth0Domain}/oauth/token`;

          const refreshParams = new URLSearchParams({
            grant_type: 'refresh_token',
            client_id: clientId,
            refresh_token: tokenData.refreshToken,
          });

          console.log(`[IPC] Requesting new token from ${tokenUrl} using refresh token.`);
          const response = await fetch(tokenUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: refreshParams,
          });

          const newTokens = await response.json();

          if (!response.ok) {
            console.error('[IPC] Refresh token exchange failed:', newTokens);
            // Clear stored tokens if refresh fails, forcing re-login
            store.delete(AUTH_TOKEN_KEY);
            stopBackgroundTokenRefresh(); // Stop background refresh when tokens are cleared
            return null;
          }

          console.log('[IPC] Refresh token exchange successful. New tokens received.');
          const newTokenData = {
            accessToken: newTokens.access_token,
            idToken: newTokens.id_token,
            refreshToken: newTokens.refresh_token || tokenData.refreshToken, // Use new refresh token if provided, else keep old
            expiresIn: newTokens.expires_in,
            scope: newTokens.scope || tokenData.scope,
            receivedAt: Date.now(),
          };
          store.set(AUTH_TOKEN_KEY, newTokenData);
          console.log('[IPC] New tokens stored.');
          
          // Ensure background refresh is running with new tokens
          startBackgroundTokenRefresh();
          
          return newTokenData.accessToken;
        } catch (error) {
          console.error('[IPC] Error during token refresh:', error);
          store.delete(AUTH_TOKEN_KEY); // Clear tokens on error
          stopBackgroundTokenRefresh(); // Stop background refresh when tokens are cleared
          return null;
        }
      } else {
        console.log('[IPC] Token expired, but no refresh token available. Clearing tokens.');
        store.delete(AUTH_TOKEN_KEY); // No refresh token, so user must re-authenticate
        stopBackgroundTokenRefresh(); // Stop background refresh when tokens are cleared
        return null;
      }
    }

    console.log('[IPC] Existing access token is valid.');
    
    // Ensure background refresh is running for valid tokens
    if (!tokenRefreshInterval) {
      startBackgroundTokenRefresh();
    }
    
    return tokenData.accessToken;
  });
  console.log("🔐 Auth0 get-access-token listener ready with refresh logic.");

  // IPC Handler for getting user information
  ipcMain.handle('get-user-info', async () => {
    console.log('[IPC] Handling get-user-info');
    const tokenData = store.get(AUTH_TOKEN_KEY);
    if (tokenData && tokenData.accessToken) {
      try {
        const auth0Domain = RENDERER_ENV_VARS.VITE_AUTH0_DOMAIN;
        const userInfoUrl = `https://${auth0Domain}/userinfo`;
        console.log(`[IPC] Fetching user info from ${userInfoUrl}`);
        const response = await fetch(userInfoUrl, {
          headers: {
            'Authorization': `Bearer ${tokenData.accessToken}`,
          },
        });
        if (!response.ok) {
          const errorData = await response.text();
          console.error(`[IPC] Error fetching user info: ${response.status}`, errorData);
          throw new Error(`Failed to fetch user info: ${response.status}`);
        }
        const userInfo = await response.json();
        console.log('[IPC] User info fetched successfully:', userInfo ? Object.keys(userInfo) : 'null');
        return userInfo;
      } catch (error) {
        console.error('[IPC] Error in get-user-info handler:', error);
        return null;
      }
    }
    console.log('[IPC] No access token available to fetch user info.');
    return null;
  });
  console.log("🔐 Auth0 get-user-info listener ready.");

  // IPC Handler for logout
  ipcMain.handle('logout', async () => {
    console.log('[IPC] Handling logout');
    try {
      // Clear local tokens
      store.delete(AUTH_TOKEN_KEY);
      console.log('[IPC] Local tokens cleared.');
      
      // Stop background token refresh
      stopBackgroundTokenRefresh();

      // Open Auth0 logout URL in system browser
      const auth0Domain = RENDERER_ENV_VARS.VITE_AUTH0_DOMAIN;
      const clientId = RENDERER_ENV_VARS.VITE_AUTH0_CLIENT_ID;
      // The returnTo URL should be a URL that Auth0 allows.
      // For production, it might be where your auth-server.js can show a "logged out" page.
      // For dev, it might be the app's base URL or a specific logout confirmation page.
      const returnToDev = 'http://localhost:5173/login'; // Example for dev
      const returnToProd = `http://localhost:8123/logout-success`; // For production server
      
      const logoutUrl = new URL(`https://${auth0Domain}/v2/logout`);
      logoutUrl.searchParams.append('client_id', clientId);
      logoutUrl.searchParams.append('returnTo', isDev ? returnToDev : returnToProd);

      console.log(`[IPC] Opening logout URL: ${logoutUrl.toString()}`);
      await shell.openExternal(logoutUrl.toString());
      
      // Notify renderer that logout process has been initiated.
      // The AuthContext will listen for 'auth-logged-out' which it should trigger itself
      // or this handler could send it. For now, AuthContext handles its state.
      if (mainWindow && mainWindow.webContents && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send('auth-logged-out'); // Explicitly send logged out event
      }
      
      return { success: true };
    } catch (error) {
      console.error('[IPC] Error during logout:', error);
      return { success: false, error: error.message || 'Logout failed' };
    }
  });
  console.log("🔐 Auth0 logout listener ready.");
}

const crypto = require('crypto'); // Add crypto for PKCE

// Helper function for PKCE: Base64 URL encoding
function base64URLEncode(str) {
  return str.toString('base64')
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=/g, '');
      }
      
// Helper function for PKCE: SHA256 hashing
function sha256(buffer) {
  return crypto.createHash('sha256').update(buffer).digest();
}

// Global variable to store PKCE verifier and state temporarily
let pkceVerifier = null;
let authState = null; // Renamed from global.auth0State for clarity

/**
 * Handle Auth0 callback data received from the system browser via the local HTTP server
 * Performs PKCE token exchange directly in the main process.
 */
async function handleAuth0Callback(params) { // Make async
  console.log('🔑 Auth0 callback received from system browser:', { 
    hasCode: !!params.code,
    hasState: !!params.state,
  });

  // --- 1. Verify State ---
  if (!authState || params.state !== authState) {
    console.error('❌ Auth0 state mismatch! Expected:', authState, 'Received:', params.state);
    authState = null; // Clear potentially compromised state
    pkceVerifier = null; // Clear verifier too
     if (mainWindow && mainWindow.webContents) {
       // Send specific error to renderer
       mainWindow.webContents.send('auth-failed', 'Authentication error: Invalid state. Please try logging in again.');
     }
    return; // Stop processing
  }
  console.log('✅ State verified.');
  const receivedState = authState; // Keep a copy before clearing
  authState = null; // Clear used state immediately

  // --- 2. Check for Errors from Auth0 ---
  if (params.error) {
      console.error('❌ Error received from Auth0 during callback:', params.error, params.error_description);
      pkceVerifier = null; // Clear verifier
      if (mainWindow && mainWindow.webContents) {
          mainWindow.webContents.send('auth-failed', `Authentication error: ${params.error_description || params.error}`);
      }
    return;
  }
  
  // --- 3. Ensure Code and Verifier Exist ---
  if (!params.code) {
      console.error('❌ Auth0 callback missing authorization code.');
      pkceVerifier = null; // Clear verifier
      if (mainWindow && mainWindow.webContents) {
          mainWindow.webContents.send('auth-failed', 'Authentication error: Missing authorization code.');
      }
      return;
  }
  if (!pkceVerifier) {
      console.error('❌ PKCE code_verifier missing. Cannot exchange code.');
      // State was already cleared
      if (mainWindow && mainWindow.webContents) {
          mainWindow.webContents.send('auth-failed', 'Internal authentication error: Missing PKCE verifier. Please try again.');
      }
      return;
  }
  console.log('✅ Code received and PKCE verifier found.');
  const code = params.code;
  const verifier = pkceVerifier; // Keep a copy before clearing
  pkceVerifier = null; // Clear used verifier

  // --- 4. Exchange Code for Tokens ---
  const auth0Domain = RENDERER_ENV_VARS.VITE_AUTH0_DOMAIN;
  const clientId = RENDERER_ENV_VARS.VITE_AUTH0_CLIENT_ID;
  const redirectUri = isDev ? 'http://localhost:5173/callback' : 'http://localhost:8123/callback'; // Use the correct URI for the server
  console.log(`[AUTH] Determined redirectUri: ${redirectUri} (isDev: ${isDev})`);

  const tokenUrl = `https://${auth0Domain}/oauth/token`;
  const tokenParams = new URLSearchParams({
      grant_type: 'authorization_code',
      client_id: clientId,
      code: code,
      code_verifier: verifier,
      redirect_uri: redirectUri,
  });

  console.log(`[AUTH] Exchanging code for token at ${tokenUrl} with client_id: ${clientId.substring(0,5)}...`);

  try {
      const response = await fetch(tokenUrl, {
          method: 'POST',
          headers: {
              'Content-Type': 'application/x-www-form-urlencoded',
          },
          body: tokenParams,
      });

      const tokens = await response.json();

      if (!response.ok) {
          console.error('❌ Error exchanging code for tokens:', tokens);
          if (mainWindow && mainWindow.webContents) {
              mainWindow.webContents.send('auth-failed', `Token exchange failed: ${tokens.error_description || tokens.error || response.statusText}`);
          }
    return;
  }
  
      console.log('✅ Tokens received successfully:', { hasAccessToken: !!tokens.access_token, hasIdToken: !!tokens.id_token, expiresIn: tokens.expires_in });

      // --- 5. Store Tokens Securely ---
      const tokenDataToStore = {
          accessToken: tokens.access_token,
          idToken: tokens.id_token, // Useful for user info
          refreshToken: tokens.refresh_token, // Important for refreshing later
          expiresIn: tokens.expires_in, // In seconds
          scope: tokens.scope,
          receivedAt: Date.now() // Store timestamp for expiry calculation
      };
      store.set(AUTH_TOKEN_KEY, tokenDataToStore);
      console.log('[AUTH] Tokens stored securely.');
      
      // Start background token refresh for new tokens
      startBackgroundTokenRefresh();

      // --- 6. Notify Renderer of Success ---
      ensureMainWindow(() => { // Ensure window exists before sending IPC
          if (mainWindow && mainWindow.webContents && !mainWindow.isDestroyed()) {
              console.log('[AUTH] Sending auth-successful IPC to renderer.');
              mainWindow.webContents.send('auth-successful');
              focusMainWindow(); // Bring window to front
          } else {
               console.error('[AUTH] Cannot send auth-successful IPC - no valid main window.');
          }
      });

  } catch (error) {
      console.error('❌ Network or unexpected error during token exchange:', error);
      if (mainWindow && mainWindow.webContents) {
          mainWindow.webContents.send('auth-failed', 'Network error during authentication. Please check your connection and try again.');
      }
  }
}

/**
 * Opens the system's default web browser to the Auth0 /authorize endpoint.
 * Generates PKCE code challenge and state parameter.
 */
function openSystemBrowserForAuth() {
  console.log('[AUTH] Initiating login flow in openSystemBrowserForAuth...');

  // Generate PKCE verifier and challenge
  pkceVerifier = base64URLEncode(crypto.randomBytes(32));
  const pkceChallenge = base64URLEncode(sha256(pkceVerifier));
  const codeChallengeMethod = 'S256';

  // Generate state
  authState = base64URLEncode(crypto.randomBytes(32)); // Store globally for callback verification

  console.log('[AUTH] Generated PKCE Challenge and State.');

  const auth0Domain = RENDERER_ENV_VARS.VITE_AUTH0_DOMAIN;
  const clientId = RENDERER_ENV_VARS.VITE_AUTH0_CLIENT_ID;
  const audience = RENDERER_ENV_VARS.VITE_AUTH0_AUDIENCE;
  // IMPORTANT: Redirect URI MUST match what's configured in Auth0 AND where your server listens
  const redirectUri = isDev 
    ? 'http://localhost:5173/callback' // Dev server handles callback directly
    : 'http://localhost:8123/callback'; // Production uses dedicated server
  console.log(`[AUTH] Determined redirectUri: ${redirectUri} (isDev: ${isDev})`);

  // Define scopes - openid, profile, email are standard, offline_access for refresh token
  const scope = 'openid profile email offline_access'; 

  const authorizeUrl = new URL(`https://${auth0Domain}/authorize`);
  authorizeUrl.searchParams.append('response_type', 'code');
  authorizeUrl.searchParams.append('client_id', clientId);
  authorizeUrl.searchParams.append('redirect_uri', redirectUri);
  authorizeUrl.searchParams.append('scope', scope);
  authorizeUrl.searchParams.append('state', authState);
  authorizeUrl.searchParams.append('code_challenge', pkceChallenge);
  authorizeUrl.searchParams.append('code_challenge_method', codeChallengeMethod);
  if (audience) {
    authorizeUrl.searchParams.append('audience', audience);
      }

  console.log(`[AUTH] Opening system browser to: https://${auth0Domain}/authorize?... (URL Params logged below)`);
  console.log('[AUTH] URL Params:', { clientId: clientId.substring(0,5)+'...', redirectUri, scope, state: '***', code_challenge: '***', code_challenge_method: codeChallengeMethod, audience });
    
  // Open the URL in the system browser
  shell.openExternal(authorizeUrl.toString()).catch(err => {
     console.error("❌ Failed to open external browser:", err);
     // Notify renderer of the failure if possible
     if (mainWindow && mainWindow.webContents) {
       mainWindow.webContents.send('auth-failed', 'Failed to open the login page in your browser.');
     }
  });
}

console.log("🐍 IPC handler 'request-restart-local-backend' (implemented) registered.");

// Global variable to track backend readiness
let isBackendReady = false;

// Function to check if local backend is ready
async function checkBackendHealth() {
  const maxAttempts = 20; // Reduced to 20 attempts since we're starting later
  const attemptInterval = 2000; // Increased to 2 seconds between attempts
  
  // Try URLs in order of likelihood to work
  const healthUrls = [
    { host: '127.0.0.1', port: 9001, path: '/health' },
    { host: 'localhost', port: 9001, path: '/health' }
  ];
  
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    console.log(`[electron.js] Checking backend health (attempt ${attempt}/${maxAttempts})...`);
    
    // Try each URL
    for (const urlConfig of healthUrls) {
      try {
        const url = `http://${urlConfig.host}:${urlConfig.port}${urlConfig.path}`;
        console.log(`[electron.js] Trying health check at: ${url}`);
        
        const isHealthy = await new Promise((resolve) => {
          const request = http.request({
            hostname: urlConfig.host,
            port: urlConfig.port,
            path: urlConfig.path,
            method: 'GET',
            timeout: 5000,
            headers: {
              'Accept': 'application/json',
              'User-Agent': 'Denker-Electron-HealthCheck'
            }
          }, (response) => {
            let data = '';
            response.on('data', (chunk) => {
              data += chunk;
            });
            response.on('end', () => {
              if (response.statusCode === 200) {
                console.log(`[electron.js] ✅ Backend is ready at ${url}! (attempt ${attempt}) Response: ${data.substring(0, 100)}`);
                resolve(true);
              } else {
                console.log(`[electron.js] Health check at ${url} returned status: ${response.statusCode} ${response.statusMessage}`);
                resolve(false);
              }
            });
          });
          
          request.on('error', (error) => {
            console.log(`[electron.js] Health check failed at ${url}: ${error.message}`);
            resolve(false);
          });
          
          request.on('timeout', () => {
            console.log(`[electron.js] Health check timeout at ${url}`);
            request.destroy();
            resolve(false);
          });
          
          request.end();
        });
        
        if (isHealthy) {
          isBackendReady = true;
          
          // Notify the frontend that backend is ready
          if (mainWindow && mainWindow.webContents && !mainWindow.isDestroyed()) {
            mainWindow.webContents.send('backend-ready');
          }
          
          return true;
        }
      } catch (error) {
        console.log(`[electron.js] Health check error: ${error.message}`);
        continue; // Try next URL
      }
    }
    
    // Wait before next attempt if all URLs failed
    if (attempt < maxAttempts) {
      console.log(`[electron.js] All health check URLs failed, waiting ${attemptInterval}ms before retry...`);
      await new Promise(resolve => setTimeout(resolve, attemptInterval));
    }
  }
  
  console.error(`[electron.js] ❌ Backend failed to become ready after ${maxAttempts} attempts`);
  
  // Notify frontend of backend failure
  if (mainWindow && mainWindow.webContents && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send('backend-failed', 'Local backend failed to respond to health checks within expected time');
  }
  
  return false;
}

// IPC handler to check if backend is ready
ipcMain.handle('is-backend-ready', () => {
  return isBackendReady;
});

// IPC handler to open a specific file path in the system's default application
ipcMain.handle('fs:openFilePath', async (event, filePath) => {
  try {
    console.log(`[electron.js] Opening file: ${filePath}`);
    
    // Check if file exists first
    if (!fs.existsSync(filePath)) {
      console.error(`[electron.js] File does not exist: ${filePath}`);
      throw new Error(`File does not exist: ${filePath}`);
    }
    
    // Use shell.openPath to open the file with the system's default application
    const result = await shell.openPath(filePath);
    
    if (result) {
      // If result is non-empty, it means there was an error
      console.error(`[electron.js] Error opening file ${filePath}: ${result}`);
      throw new Error(`Failed to open file: ${result}`);
    }
    
    console.log(`[electron.js] Successfully opened file: ${filePath}`);
    return { success: true };
    
  } catch (error) {
    console.error(`[electron.js] Error opening file ${filePath}:`, error);
    return { 
      success: false, 
      error: error.message || 'Failed to open file' 
    };
  }
});