console.log("### EXECUTING frontend/public/electron.js - VERSION XYZ ###");
const fs = require('fs');
const path = require('path');
const os = require('os');
const http = require('http');
const url = require('url');
const { createAuthServer } = require('./auth-server');
const startupLogPath = path.join(os.homedir(), 'denker_electron_startup_log.txt');
fs.writeFileSync(startupLogPath, `Electron main process (electron.js) started at ${new Date().toISOString()}\n`, { flag: 'a' });

console.log('🚀 electron.js script started. Timestamp:', Date.now());
fs.appendFileSync(startupLogPath, `Initial console.log in electron.js executed at ${new Date().toISOString()}\n`);
const { app, BrowserWindow, ipcMain, globalShortcut, screen, Tray, Menu, clipboard, dialog, desktopCapturer, protocol, shell } = require('electron');
fs.appendFileSync(startupLogPath, `Electron modules imported at ${new Date().toISOString()}\n`);
const isDev = process.env.NODE_ENV === 'development';
if (isDev) {
  require('dotenv').config({ path: path.join(__dirname, '../.env') });
}

// Initialize store for app settings
const Store = require('electron-store');

// Initialize store for app settings
const store = new Store();

// Keep a global reference of the windows and servers
let mainWindow = null;
let subWindow = null;
let tray = null;
let authServer = null;

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
const API_URL = process.env.VITE_API_URL || 'http://127.0.0.1:8001/api/v1';

// Ensure WS_URL is the base URL without /api/v1
// let rawWsUrl = process.env.VITE_WS_URL;
// if (rawWsUrl) {
//   // If VITE_WS_URL is set, remove /api/v1 if it exists at the end
//   rawWsUrl = rawWsUrl.replace(/\/api\/v1\/?$/, '');
// }
// const WS_URL = rawWsUrl || 'ws://127.0.0.1:8001'; // Default if not set or after stripping
// console.log('[electron.js] Determined WS_URL:', WS_URL); // Debug log

let determinedWsUrl;
const envWsUrl = process.env.VITE_WS_URL;

if (envWsUrl) {
    try {
        const parsedUrl = new URL(envWsUrl);
        determinedWsUrl = `${parsedUrl.protocol}//${parsedUrl.host}`; // Reconstruct without path
        console.log(`[electron.js] Used envWsUrl ('${envWsUrl}') and reconstructed to: ${determinedWsUrl}`);
    } catch (e) {
        console.warn(`[electron.js] process.env.VITE_WS_URL ('${envWsUrl}') is invalid, falling back to default. Error: ${e.message}`);
        determinedWsUrl = 'ws://127.0.0.1:8001';
    }
} else {
    console.log('[electron.js] process.env.VITE_WS_URL not set, using default.');
    determinedWsUrl = 'ws://127.0.0.1:8001';
}

const WS_URL = determinedWsUrl;
console.log('[electron.js] Final Determined WS_URL:', WS_URL);

const API_KEY = process.env.VITE_API_KEY;

// Store the API URLs for use in the renderer
const RENDERER_ENV_VARS = {
  VITE_API_URL: API_URL,
  VITE_WS_URL: WS_URL, // This will now be correctly ws://127.0.0.1:8001
  VITE_API_KEY: API_KEY,
  // Add Auth0 configuration with hard-coded fallbacks for production
  VITE_AUTH0_DOMAIN: process.env.VITE_AUTH0_DOMAIN || 'auth.denker.ai',
  VITE_AUTH0_CLIENT_ID: process.env.VITE_AUTH0_CLIENT_ID || 'lq6uzeeUp9i14E8FNpJwr0DVIP5VtOzQ',
  VITE_AUTH0_AUDIENCE: process.env.VITE_AUTH0_AUDIENCE || 'https://api.denker.ai',
  VITE_NODE_ENV: process.env.VITE_NODE_ENV || (isDev ? 'development' : 'production')
};

console.log('🔧 Environment variables for renderer:', {
  VITE_AUTH0_DOMAIN: RENDERER_ENV_VARS.VITE_AUTH0_DOMAIN,
  VITE_AUTH0_CLIENT_ID: RENDERER_ENV_VARS.VITE_AUTH0_CLIENT_ID ? RENDERER_ENV_VARS.VITE_AUTH0_CLIENT_ID.substring(0, 8) + '...' : 'MISSING',
  VITE_AUTH0_AUDIENCE: RENDERER_ENV_VARS.VITE_AUTH0_AUDIENCE,
  VITE_NODE_ENV: RENDERER_ENV_VARS.VITE_NODE_ENV,
  isDev
});

// Parse any command line arguments
let deeplinkingUrl;

console.log('🚀 electron.js: About to attach app.whenReady() handler for main window creation. Timestamp:', Date.now());
fs.appendFileSync(startupLogPath, `app.whenReady handler attached at ${new Date().toISOString()}\n`);
app.whenReady().then(() => {
  fs.appendFileSync(startupLogPath, `app.whenReady resolved at ${new Date().toISOString()}\n`);
  console.log('🚀 electron.js: app.whenReady() for main window creation has resolved. Timestamp:', Date.now());

  console.log('🚀 electron.js: Calling createMainWindow() from app.whenReady(). Timestamp:', Date.now());
  setupAuth0Authentication();
  createMainWindow();
  registerGlobalShortcut();
  setupClipboardMonitor();
  setupAppMenu();

  // --- ADD IPC Handlers for Auth --- 
  console.log('[*] Registering Auth IPC Handlers...');
  
  // Handler for renderer to request access token
  ipcMain.handle('get-access-token', async () => {
    const tokens = store.get(AUTH_TOKEN_KEY);
    if (!tokens || !tokens.accessToken) {
      console.log('[IPC get-access-token] No access token found.');
      return null;
}

    // **TODO: Implement token expiry check and refresh logic here**
    const expiryTime = tokens.receivedAt + (tokens.expiresIn * 1000);
    if (Date.now() >= expiryTime) {
        console.warn('[IPC get-access-token] Access token expired. Need refresh logic.');
        // Attempt refresh here if refreshToken exists
        // For now, return null, forcing re-login potentially
        store.delete(AUTH_TOKEN_KEY); // Clear expired tokens
        return null;
    }
  
    console.log('[IPC get-access-token] Returning stored access token.');
    return tokens.accessToken;
  });
    
  // --- ADDED: Handler for renderer to request user info --- 
  ipcMain.handle('get-user-info', async () => {
    const tokens = store.get(AUTH_TOKEN_KEY);
    if (!tokens || !tokens.idToken) {
      console.log('[IPC get-user-info] No ID token found.');
      return null;
    }
    
    try {
      // Simple JWT decode (Payload only, no signature verification)
      const payloadBase64 = tokens.idToken.split('.')[1];
      const decodedJson = Buffer.from(payloadBase64, 'base64').toString('utf-8');
      const payload = JSON.parse(decodedJson);
    
      // Extract common profile claims
      const userInfo = {
        name: payload.name,
        nickname: payload.nickname,
        picture: payload.picture,
        email: payload.email,
        email_verified: payload.email_verified,
        sub: payload.sub // Subject (user ID)
      };
  
      console.log('[IPC get-user-info] Returning user info:', { name: userInfo.name, email: userInfo.email });
      return userInfo;
    } catch (error) {
      console.error('[IPC get-user-info] Error decoding ID token:', error);
      return null; // Return null if decoding fails
    }
  });
  
  // Handler for renderer to initiate logout
  ipcMain.handle('logout', async () => {
    console.log('🚪 Received logout request from renderer');
    const tokens = store.get(AUTH_TOKEN_KEY);
    store.delete(AUTH_TOKEN_KEY); // Clear local tokens immediately
    console.log('[IPC logout] Local tokens cleared.');

    const auth0Domain = RENDERER_ENV_VARS.VITE_AUTH0_DOMAIN;
    const clientId = RENDERER_ENV_VARS.VITE_AUTH0_CLIENT_ID;
    
    // Determine the correct returnTo URL based on environment
    const returnTo = isDev 
      ? 'http://localhost:5173' // Dev returns to Vite server (or wherever your app is)
      : 'http://localhost:8123/logout-success'; // Packaged app returns to our local auth server's logout page

    console.log(`[IPC logout] Using returnTo URL: ${returnTo}`);

    const logoutUrl = new URL(`https://${auth0Domain}/v2/logout`);
    logoutUrl.searchParams.append('client_id', clientId);
    logoutUrl.searchParams.append('returnTo', returnTo); 

    try {
      console.log(`[IPC logout] Opening external browser for Auth0 logout: ${logoutUrl.toString()}`);
      await shell.openExternal(logoutUrl.toString());
      // Notify renderer that logout process started (optional, depends on desired UX)
      if (mainWindow && mainWindow.webContents) {
        mainWindow.webContents.send('auth-logged-out');
    }
      return { success: true };
  } catch (error) {
      console.error('❌ Failed to open external browser for logout:', error);
      return { success: false, error: error.message || 'Failed to start logout process.' };
    }
  });
  
  // Remove potentially conflicting old handlers if they exist
  console.log('[*] Cleaning up old IPC Handlers...');
  ipcMain.removeHandler('send-redirect-callback'); 
  ipcMain.removeHandler('handle-auth0-callback'); 
  // Add any others you might have used previously
  console.log('[*] IPC Handler setup complete.');
  // --- END Auth IPC Handlers ---

  // IPC handler to provide environment variables to the renderer
  ipcMain.handle('get-renderer-env-vars', () => {
    console.log('[electron.js IPC] Request received for RENDERER_ENV_VARS.');
    console.log('[electron.js IPC] Current RENDERER_ENV_VARS.VITE_WS_URL is:', RENDERER_ENV_VARS.VITE_WS_URL);
    console.log('[electron.js IPC] Current RENDERER_ENV_VARS.VITE_API_URL is:', RENDERER_ENV_VARS.VITE_API_URL);
    console.log('[electron.js IPC] Current RENDERER_ENV_VARS.VITE_NODE_ENV is:', RENDERER_ENV_VARS.VITE_NODE_ENV);
    return RENDERER_ENV_VARS;
  });

  app.on('activate', function () {
    console.log('🚀 electron.js: app.on(\'activate\') triggered. Timestamp:', Date.now());
    if (BrowserWindow.getAllWindows().length === 0) createMainWindow();
  });
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
  globalShortcut.register('CommandOrControl+Shift+D', async () => {
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
        const sources = await desktopCapturer.getSources({
          types: ['window'],
          thumbnailSize: { width: 1920, height: 1080 }
        });
        console.log('📸 Available windows:', sources.map(s => s.name));

        // Filter out Denker windows and system windows
        const filteredSources = sources.filter(source => {
          const name = source.name.toLowerCase();
          return !name.includes('denker') && 
                 !name.includes('electron') && 
                 !name.includes('cursor') &&
                 !name.includes('system') &&
                 !name.includes('finder') &&
                 !name.includes('terminal');
        });

        if (filteredSources.length > 0) {
          // Get the most recently active window
          const activeWindow = filteredSources[0];
          console.log('📸 Selected window:', activeWindow.name);
          screenshot = activeWindow.thumbnail.toDataURL();
          console.log('📸 Screenshot captured successfully');
        } else {
          console.log('⚠️ No suitable window found for capture');
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
      const apiRequest = {
        query_id: `query_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`,
        text: clipboardText,
        screenshot: screenshot,
        mode: mode
      };

      try {
        console.log('🔄 Starting API request...');
        const requestStartTime = Date.now();
        
        const response = await fetch(`${API_URL}/agents/intention`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${API_KEY}`
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
      subWindow.webTools.openDevTools({ mode: 'detach' });
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

// Clean up before quitting
app.on('before-quit', () => {
  console.log('Before quit event received - setting app.isQuitting to true');
  // Mark that we're quitting
  app.isQuitting = true;
  
  // Clean up resources
  if (clipboardMonitorInterval) {
    clearInterval(clipboardMonitorInterval);
    console.log('Cleared clipboard monitor interval');
  }
  
  // Clean up tray if it exists
  if (tray) {
    tray.destroy();
    tray = null;
    console.log('Destroyed tray');
  }
  
  // Ensure we're forcefully quitting
  setTimeout(() => {
    console.log('Force exit after timeout');
    process.exit(0);
  }, 1000);
});

// Add additional quit handler to ensure app closes
app.on('quit', () => {
  console.log('App quit event received');
  // Force quit as a last resort
  process.exit(0);
});

// Force quit when all windows are closed on macOS
app.on('window-all-closed', () => {
  console.log('All windows closed, quitting app');
  app.isQuitting = true;
  app.quit();
});

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
        app.isQuitting = true;
        app.quit();
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
            // Force aggressive quit
            app.isQuitting = true;
            
            // Destroy windows explicitly
            if (subWindow) {
              subWindow.destroy();
              subWindow = null;
            }
            
            if (mainWindow) {
              mainWindow.removeAllListeners('close');
              mainWindow.destroy();
              mainWindow = null;
            }
            
            // Force app to quit
            app.quit();
            
            // As a last resort, exit the process after a short delay
            setTimeout(() => {
              process.exit(0);
            }, 500);
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
  // This should remain as is
  ipcMain.handle('login', async () => { // Changed to handle, can be async if needed
    console.log('🔓 Received login request from renderer');
    try {
      openSystemBrowserForAuth(); // Call the function to open browser with PKCE
      return { success: true }; // Indicate the process started
    } catch (error) {
       console.error("❌ Error initiating login:", error);
       return { success: false, error: error.message || 'Failed to start login process.' };
    }
  });
  console.log("🔐 Auth0 login request listener ('login') ready.");

  // ... other potential handlers like 'logout', 'getAccessToken', 'getUserInfo' should be here ...
  // Ensure ipcMain.handle('logout', ...) is correctly defined
  // Ensure ipcMain.handle('getAccessToken', ...) is correctly defined
  // Ensure ipcMain.handle('getUserInfo', ...) is correctly defined
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