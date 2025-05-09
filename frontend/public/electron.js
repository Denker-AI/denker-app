const { app, BrowserWindow, ipcMain, globalShortcut, screen, Tray, Menu, clipboard, dialog, desktopCapturer } = require('electron');
const path = require('path');
const isDev = require('electron-is-dev');
const Store = require('electron-store');

// Load environment variables from .env file when in development
if (isDev) {
  require('dotenv').config({ path: path.join(__dirname, '../.env') });
}

// Initialize store for app settings
const store = new Store();

// Keep a global reference of the windows
let mainWindow = null;
let subWindow = null;
let tray = null;

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
const WS_URL = process.env.VITE_WS_URL || 'ws://127.0.0.1:8001/api/v1';
const API_KEY = process.env.VITE_API_KEY;

// Store the API URLs for use in the renderer
const RENDERER_ENV_VARS = {
  VITE_API_URL: API_URL,
  VITE_WS_URL: WS_URL,
  VITE_API_KEY: API_KEY,
  // Add Auth0 configuration
  VITE_AUTH0_DOMAIN: process.env.VITE_AUTH0_DOMAIN,
  VITE_AUTH0_CLIENT_ID: process.env.VITE_AUTH0_CLIENT_ID,
  VITE_AUTH0_AUDIENCE: process.env.VITE_AUTH0_AUDIENCE,
  VITE_NODE_ENV: process.env.VITE_NODE_ENV || (isDev ? 'development' : 'production')
};

// Parse any command line arguments
let deeplinkingUrl;

// This needs to happen before the app is ready
// Handle the custom protocol (deep linking)
if (process.defaultApp) {
  // In development with Electron default app
  if (process.argv.length >= 2) {
    app.setAsDefaultProtocolClient('denker', process.execPath, [path.resolve(process.argv[1])]);
  }
} else {
  // In production
  app.setAsDefaultProtocolClient('denker');
}

// Handle protocol URL (macOS)
app.on('open-url', (event, url) => {
  event.preventDefault();
  deeplinkingUrl = url;
  console.log('Protocol URL detected on macOS:', url);
  
  // If the app is already running, send the URL to the main window
  if (mainWindow && mainWindow.webContents) {
    mainWindow.webContents.send('deeplink-url', url);
    
    // For Auth0 callback, also strip the protocol part and send as a hash route
    if (url.includes('callback')) {
      const hashRoute = '#/callback';
      mainWindow.webContents.send('auth0-callback', hashRoute);
      
      // Also set the window location to the callback route
      mainWindow.webContents.executeJavaScript(`window.location.hash = '/callback';`);
    }
    
    // Restore the window if minimized
    if (mainWindow.isMinimized()) {
      mainWindow.restore();
    }
    mainWindow.focus();
  }
});

// Windows deep linking handler
app.on('second-instance', (event, commandLine, workingDirectory) => {
  console.log('Second instance detected with args:', commandLine);
  
  // Someone tried to run a second instance, we should focus our window.
  if (mainWindow) {
    if (mainWindow.isMinimized()) {
      mainWindow.restore();
    }
    mainWindow.focus();
    
    // Check if there's a URL in the command line (deep linking)
    const deepLinkUrl = commandLine.find(arg => arg.startsWith('denker://'));
    if (deepLinkUrl) {
      console.log('Protocol URL detected on Windows:', deepLinkUrl);
      mainWindow.webContents.send('deeplink-url', deepLinkUrl);
      
      // For Auth0 callback, also strip the protocol part and send as a hash route
      if (deepLinkUrl.includes('callback')) {
        const hashRoute = '#/callback';
        mainWindow.webContents.send('auth0-callback', hashRoute);
        
        // Also set the window location to the callback route
        mainWindow.webContents.executeJavaScript(`window.location.hash = '/callback';`);
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
      : `file://${path.join(__dirname, '../build/index.html#/subwindow')}`;
    
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
  mainWindow = new BrowserWindow({
    width: calculateWindowWidth(),
    height: screen.getPrimaryDisplay().workAreaSize.height,
    x: screen.getPrimaryDisplay().workAreaSize.width - calculateWindowWidth(),
    y: 0,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js'),
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
    : `file://${path.join(__dirname, '../build/index.html#/')}`;
  
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

// App ready event
app.whenReady().then(() => {
  createMainWindow();
  registerGlobalShortcut();
  setupClipboardMonitor();
  // Disable tray icon creation
  // createTray();
  setupAppMenu();
  
  app.on('activate', function () {
    if (BrowserWindow.getAllWindows().length === 0) createMainWindow();
  });
});

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