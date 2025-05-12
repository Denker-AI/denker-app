console.log('🌍 Preload script TOP LEVEL started. Timestamp:', Date.now());
try {
const { contextBridge, ipcRenderer } = require('electron');

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
  // Broadcast to any listeners
  window.dispatchEvent(new CustomEvent('api-loading', { detail: isLoading }));
});

  // Listen for navigation events
  ipcRenderer.on('navigate', (event, path) => {
    console.log('preload: received navigate event to path:', path);
    // Broadcast to any listeners
    window.dispatchEvent(new CustomEvent('navigate', { detail: path }));
  });

  console.log('🌍 Preload script: Attempting to expose electron API via contextBridge. Timestamp:', Date.now());
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
          const args = process.argv; // Command line arguments passed to the renderer process
          const getArgValue = (argName) => {
            const fullArgName = `--${argName}=`;
            const arg = args.find(a => a.startsWith(fullArgName));
            return arg ? arg.substring(fullArgName.length) : undefined;
          };
      
          // Determine if running in a development-like environment based on arguments or typical Node.js env var
          // This is tricky in preload. Best if VITE_NODE_ENV is reliably passed from main.
          const nodeEnvArg = getArgValue('node-env');
          const isLikelyDev = nodeEnvArg === 'development' || process.env.NODE_ENV === 'development';


          const envVars = {
            VITE_AUTH0_DOMAIN: getArgValue('auth0-domain') || 'auth.denker.ai', // Fallback to your custom domain
            VITE_AUTH0_CLIENT_ID: getArgValue('auth0-client-id') || 'lq6uzeeUp9i14E8FNpJwr0DVIP5VtOzQ', // Your actual client ID as fallback
            VITE_AUTH0_AUDIENCE: getArgValue('auth0-audience') || 'https://api.denker.ai', // Your actual audience as fallback
            VITE_API_URL: getArgValue('api-url') || 'http://localhost:8001/api/v1', // Example fallback
            VITE_WS_URL: getArgValue('ws-url') || 'ws://127.0.0.1:8001/api/v1', // Example fallback
            VITE_NODE_ENV: nodeEnvArg || (isLikelyDev ? 'development' : 'production')
          };
          
          console.log('Preload SCRIPT providing these ENV VARS to renderer via process.argv parsing:', {
            VITE_AUTH0_DOMAIN: envVars.VITE_AUTH0_DOMAIN,
            VITE_AUTH0_CLIENT_ID: envVars.VITE_AUTH0_CLIENT_ID ? envVars.VITE_AUTH0_CLIENT_ID.substring(0, 8) + '...' : 'MISSING',
            VITE_AUTH0_AUDIENCE: envVars.VITE_AUTH0_AUDIENCE,
            VITE_NODE_ENV: envVars.VITE_NODE_ENV,
            NODE_ENV_FROM_PRELOAD_PROCESS_ENV: process.env.NODE_ENV, // For debugging what preload sees
            ALL_PROCESS_ARGS_IN_PRELOAD: process.argv.join(' ') // For debugging
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
        
        // Auth0 authentication
        login: () => {
          console.log('🔐 Requesting Auth0 login via external browser (invoking \'login\')');
          return ipcRenderer.invoke('login'); // Use invoke and the correct handler name
        },
        getAccessToken: () => ipcRenderer.invoke('get-access-token'),
        logout: () => ipcRenderer.invoke('logout'),
        getUserInfo: () => ipcRenderer.invoke('get-user-info'),
        
        // NEW: Listeners for auth state changes from main process
        onAuthSuccessful: (callback) => {
          const handler = () => callback();
          ipcRenderer.on('auth-successful', handler);
          return () => ipcRenderer.removeListener('auth-successful', handler);
        },
        onAuthFailed: (callback) => {
          const handler = (event, errorInfo) => callback(errorInfo);
          ipcRenderer.on('auth-failed', handler);
          return () => ipcRenderer.removeListener('auth-failed', handler);
        },
        onAuthLoggedOut: (callback) => {
          const handler = () => callback();
          ipcRenderer.on('auth-logged-out', handler);
          return () => ipcRenderer.removeListener('auth-logged-out', handler);
        },
        
        // Listener for deep linking events (Keep this if needed for other purposes)
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
    if (typeof window !== 'undefined') {
      window.electronIsPreloadedByScript = true;
      console.log('🌍 window.electronIsPreloadedByScript SET TO TRUE');
    } else {
      console.warn('Preload: window object is undefined after contextBridge success.');
    }
  } catch (e_contextBridge) {
    console.error('❌ Preload script: FAILED to expose electron API via contextBridge. Timestamp:', Date.now(), e_contextBridge);
    if (typeof window !== 'undefined') {
      window.electronIsPreloadedByScript = false; // Explicitly set to false on error
      console.warn('Preload: window.electronIsPreloadedByScript SET TO FALSE due to contextBridge error.');
    } else {
      console.warn('Preload: window object is undefined during contextBridge error handling.');
    }
  }

  console.log('🌍 Preload script finished execution (before outer catch). Timestamp:', Date.now());

  // Listen for messages directly from the main process
  ipcRenderer.on('store-updated', (_, data) => {
    document.dispatchEvent(new CustomEvent('store-updated', { detail: data }));
  });

  // Listen for API loading state updates
  ipcRenderer.on('api-loading', (_, isLoading) => {
    document.dispatchEvent(new CustomEvent('api-loading', { detail: isLoading }));
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
      } else {
        console.warn('⚠️ window.location not available in preload for hash setting.');
      }
    } catch (error) {
      console.error('❌ Error handling Auth0 callback in preload:', error);
    }
  });
} catch (e_outer) {
  console.error('💥💥💥 CRITICAL PRELOAD SCRIPT FAILURE (OUTER CATCH) 💥💥💥:', e_outer, 'Timestamp:', Date.now());
}
