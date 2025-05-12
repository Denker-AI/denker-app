console.log('🌍 Preload script TOP LEVEL started. Timestamp:', Date.now());
try {
  const { contextBridge, ipcRenderer } = require('electron');
  const fs = require('fs');
  const path = require('path');

  // Determine log path - robustly try to get home directory
  let logDir = '';
  try {
    logDir = process.env.HOME || process.env.USERPROFILE || (process.platform === 'win32' ? process.env.APPDATA : '/tmp');
    if (!logDir) { // Fallback if somehow still undefined
        logDir = path.join('.', 'denker_logs'); // Log to current dir subfolder as last resort
        if (!fs.existsSync(logDir)) fs.mkdirSync(logDir, { recursive: true });
    }
  } catch (e) {
    console.error("Preload: Error determining log directory base:", e);
    logDir = '.'; // Simplest fallback
  }
  const preloadLogPath = path.join(logDir, 'denker_preload_log.txt');
  
  function logToFile(message) {
    try {
      const timestamp = new Date().toISOString();
      fs.appendFileSync(preloadLogPath, `${timestamp}: ${message}\\n`);
      console.log(`[PRELOAD_FILE_LOG] ${message}`); // Also log to console if possible
    } catch (e) {
      console.error("Preload: FAILED TO WRITE TO LOG FILE:", e, "Original message:", message);
    }
  }

  logToFile('Preload script TOP LEVEL started.');

  // Create a promise-based queue for capture data
  let captureDataQueue = [];
  let waitingResolvers = [];

  // Listen for capture data from main process
  ipcRenderer.on('capture-data', (event, data) => {
    console.log('preload: received capture-data event:', {
      mode: data.mode,
      hasText: !!data.text,
      textLength: data.text?.length || 0,
      textPreview: data.text?.substring(0, 100) + '...',
      hasScreenshot: !!data.screenshot,
      screenshotLength: data.screenshot?.length || 0,
      timestamp: data.timestamp,
      clipboardAge: data.clipboardAge
    });

    if (waitingResolvers.length > 0) {
      // If someone is waiting, resolve their promise immediately
      const resolve = waitingResolvers.shift();
      resolve(data);
    } else {
      // Otherwise queue the data
      captureDataQueue.push(data);
    }
  });

  // Listen for API loading state
  ipcRenderer.on('api-loading', (event, isLoading) => {
    console.log('preload: received api-loading event:', isLoading);
    logToFile(`Received api-loading event: ${isLoading}`);
    // Broadcast to any listeners
    window.dispatchEvent(new CustomEvent('api-loading', { detail: isLoading }));
  });

  // Listen for navigation events
  ipcRenderer.on('navigate', (event, path) => {
    console.log('preload: received navigate event to path:', path);
    logToFile(`Received navigate event to path: ${path}`);
    // Broadcast to any listeners
    window.dispatchEvent(new CustomEvent('navigate', { detail: path }));
  });

  console.log('🌍 Preload script: Attempting to expose electron API via contextBridge. Timestamp:', Date.now());
  logToFile('Attempting to expose electron API via contextBridge.');
  try {
    contextBridge.exposeInMainWorld(
      'electron',
      {
        // Window management
        openMainWindow: () => ipcRenderer.invoke('open-main-window'),
        closeSubWindow: () => ipcRenderer.invoke('close-sub-window'),
        minimizeMainWindow: () => ipcRenderer.invoke('minimize-main-window'),
        toggleTransparency: (isTransparent) => ipcRenderer.invoke('toggle-transparency', isTransparent),
        
        // Environment variables
        getEnvVars: () => {
          // Create a new object with our environment variables and fallbacks
          const envVars = {
            ...process.env,
            // Add hard-coded fallbacks for Auth0 configuration
            VITE_AUTH0_DOMAIN: process.env.VITE_AUTH0_DOMAIN || 'auth.denker.ai',
            VITE_AUTH0_CLIENT_ID: process.env.VITE_AUTH0_CLIENT_ID || 'lq6uzeeUp9i14E8FNpJwr0DVIP5VtOzQ',
            VITE_AUTH0_AUDIENCE: process.env.VITE_AUTH0_AUDIENCE || 'https://api.denker.ai',
            VITE_NODE_ENV: process.env.VITE_NODE_ENV || (process.env.NODE_ENV === 'development' ? 'development' : 'production')
          };
          
          console.log('Preload providing env vars to renderer:', {
            VITE_AUTH0_DOMAIN: envVars.VITE_AUTH0_DOMAIN,
            VITE_AUTH0_CLIENT_ID: envVars.VITE_AUTH0_CLIENT_ID ? envVars.VITE_AUTH0_CLIENT_ID.substring(0, 8) + '...' : 'MISSING',
            VITE_AUTH0_AUDIENCE: envVars.VITE_AUTH0_AUDIENCE,
            NODE_ENV: envVars.NODE_ENV,
            VITE_NODE_ENV: envVars.VITE_NODE_ENV
          });
          
          return envVars;
        },
        
        // API configuration
        getApiUrl: () => {
          const args = process.argv;
          const apiUrlArg = args.find(arg => arg.startsWith('--api-url='));
          return apiUrlArg ? apiUrlArg.replace('--api-url=', '') : (process.env.VITE_API_URL || 'http://localhost:8001/api/v1');
        },
        getApiKey: () => ipcRenderer.invoke('get-api-key'),
        
        // Data capture
        waitForCaptureData: () => new Promise((resolve) => {
          // If we have queued data, resolve immediately
          if (captureDataQueue.length > 0) {
            const data = captureDataQueue.shift();
            console.log('preload: resolving with queued data:', {
              mode: data.mode,
              hasText: !!data.text,
              textLength: data.text?.length || 0,
              hasScreenshot: !!data.screenshot,
              screenshotLength: data.screenshot?.length || 0
            });
            resolve(data);
            return;
          }

          // Add to waiting resolvers
          console.log('preload: adding resolver to queue');
          waitingResolvers.push(resolve);
        }),
        
        // API response handling
        waitForApiResponse: () => new Promise((resolve) => {
          ipcRenderer.once('api-response', (event, response) => resolve(response));
        }),
        
        waitForApiError: () => new Promise((resolve) => {
          ipcRenderer.once('api-error', (event, error) => resolve(error));
        }),
        
        // Loading state
        onApiLoadingChange: (callback) => {
          const handler = (event) => callback(event.detail);
          window.addEventListener('api-loading', handler);
          return () => window.removeEventListener('api-loading', handler);
        },
        
        // Option selection
        sendSelectedOption: (option) => ipcRenderer.invoke('send-selected-option', option),
        onSelectedOption: (callback) => {
          ipcRenderer.on('selected-option', (event, option) => callback(option));
          return () => ipcRenderer.removeAllListeners('selected-option');
        },
        
        // Screenshot and text capture
        getSelectedText: () => ipcRenderer.invoke('get-selected-text'),
        captureScreenshot: () => ipcRenderer.invoke('capture-screenshot'),
        
        // File system operations
        openFile: async () => ipcRenderer.invoke('dialog:openFile'),
        showDenkerFolder: () => ipcRenderer.invoke('fs:showDenkerFolder'),
        downloadFile: (fileId) => ipcRenderer.invoke('fs:downloadFile', fileId),
        
        // Clipboard operations
        writeToClipboard: (text) => ipcRenderer.invoke('clipboard:write', text),
        readFromClipboard: () => ipcRenderer.invoke('clipboard:read'),
        
        // Window operations
        minimizeToSystemTray: () => ipcRenderer.invoke('window:minimizeToSystemTray'),
        toggleAlwaysOnTop: () => ipcRenderer.invoke('window:toggleAlwaysOnTop'),
        
        // Listener for Auth0 callback events
        onAuth0Callback: (callback) => {
          ipcRenderer.on('auth0-callback', (_, callbackPath) => {
            console.log('🔑 Auth0 callback received in preload with path:', callbackPath);
            try {
              const eventDetail = typeof callbackPath === 'string' ? callbackPath : '/callback';
              console.log('🔄 Dispatching auth0-callback-received event with detail:', eventDetail);
              document.dispatchEvent(new CustomEvent('auth0-callback-received', { detail: eventDetail }));
              if (window.location) {
                console.log('🔀 Attempting to set window.location.hash in preload to:', eventDetail);
                window.location.hash = eventDetail;
                console.log('📌 Preload window.location.hash is now:', window.location.hash);
                logToFile(`Auth0 callback: window.location.hash set to ${window.location.hash}.`);
              }
              if(typeof callback === 'function') callback(eventDetail);
            } catch (error) {
              console.error('❌ Error handling Auth0 callback in preload:', error);
              logToFile(`Error handling Auth0 callback in preload: ${error.message}. Stack: ${error.stack}`);
            }
          });
        },
        
        // Listener for deep linking events
        onDeepLink: (callback) => {
          ipcRenderer.on('deeplink-url', (_, url) => {
            callback(url);
          });
        },
        
        // General utility functions
        exitApp: () => ipcRenderer.invoke('app:exit')
      }
    );
    console.log('✅ Preload script: Successfully exposed electron API. Timestamp:', Date.now());
    logToFile('Successfully exposed electron API via contextBridge.');
    if (typeof window !== 'undefined') {
      window.electronIsPreloadedByScript = true;
      console.log('🌍 window.electronIsPreloadedByScript SET TO TRUE');
      logToFile('window.electronIsPreloadedByScript SET TO TRUE.');
    } else {
      logToFile('window object is undefined after contextBridge success.');
    }
  } catch (e_contextBridge) {
    console.error('❌ Preload script: FAILED to expose electron API via contextBridge. Timestamp:', Date.now(), e_contextBridge);
    logToFile(`FAILED to expose electron API via contextBridge: ${e_contextBridge.message}. Stack: ${e_contextBridge.stack}`);
    if (typeof window !== 'undefined') {
      window.electronIsPreloadedByScript = false; // Explicitly set to false on error
      logToFile('window.electronIsPreloadedByScript SET TO FALSE due to contextBridge error.');
    } else {
      logToFile('window object is undefined during contextBridge error handling.');
    }
  }

  console.log('🌍 Preload script finished execution (before outer catch). Timestamp:', Date.now());
  logToFile('Preload script finished execution (before outer catch).');

  // Listen for messages directly from the main process
  ipcRenderer.on('store-updated', (_, data) => {
    document.dispatchEvent(new CustomEvent('store-updated', { detail: data }));
  });

  // Listen for API loading state updates
  ipcRenderer.on('api-loading', (_, isLoading) => {
    document.dispatchEvent(new CustomEvent('api-loading', { detail: isLoading }));
    logToFile(`(Duplicate listener) Received api-loading event: ${isLoading}`);
  });

  // Expose the listener for Auth0 callback in the window context directly
  ipcRenderer.on('auth0-callback', (_, callbackPath) => {
    console.log('🔑 Auth0 callback received in preload with path:', callbackPath);
    try {
      const eventDetail = typeof callbackPath === 'string' ? callbackPath : '/callback'; // Ensure it's a string
      console.log('🔄 Dispatching auth0-callback-received event with detail:', eventDetail);
      document.dispatchEvent(new CustomEvent('auth0-callback-received', { detail: eventDetail }));
      
      if (window.location) {
        console.log('🔀 Attempting to set window.location.hash in preload to:', eventDetail);
        window.location.hash = eventDetail;
        console.log('📌 Preload window.location.hash is now:', window.location.hash);
        logToFile(`Auth0 callback: window.location.hash set to ${window.location.hash}.`);
      } else {
        console.warn('⚠️ window.location not available in preload for hash setting.');
      }
    } catch (error) {
      console.error('❌ Error handling Auth0 callback in preload:', error);
      logToFile(`Error handling Auth0 callback in preload: ${error.message}. Stack: ${error.stack}`);
    }
  });
} catch (e_outer) {
  console.error('💥💥💥 CRITICAL PRELOAD SCRIPT FAILURE (OUTER CATCH) 💥💥💥:', e_outer, 'Timestamp:', Date.now());
  // Ensure logToFile is defined or attempt to define it minimally if outer error is very early
  const fs_outer = require('fs');
  const path_outer = require('path');
  let logDir_outer = '';
   try {
    logDir_outer = process.env.HOME || process.env.USERPROFILE || (process.platform === 'win32' ? process.env.APPDATA : '/tmp') || '.';
  } catch(_) { logDir_outer = '.'; }
  const preloadLogPath_outer = path_outer.join(logDir_outer, 'denker_preload_CRITICAL_ERROR_log.txt');
  try {
    const timestamp = new Date().toISOString();
    fs_outer.appendFileSync(preloadLogPath_outer, `${timestamp}: CRITICAL PRELOAD SCRIPT FAILURE (OUTER CATCH): ${e_outer.message}. Stack: ${e_outer.stack}\\n`);
  } catch (e_log) {
    console.error("Preload: FAILED TO WRITE CRITICAL ERROR TO LOG FILE:", e_log);
  }
}
