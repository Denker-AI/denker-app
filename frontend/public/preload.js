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
      // Return all environment variables so they can be used in the renderer
      return process.env;
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
      ipcRenderer.on('auth0-callback', (_, hashRoute) => {
        callback(hashRoute);
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

// Listen for messages directly from the main process
ipcRenderer.on('store-updated', (_, data) => {
  document.dispatchEvent(new CustomEvent('store-updated', { detail: data }));
});

// Listen for API loading state updates
ipcRenderer.on('api-loading', (_, isLoading) => {
  document.dispatchEvent(new CustomEvent('api-loading', { detail: isLoading }));
});

// Expose the listener for Auth0 callback in the window context directly
ipcRenderer.on('auth0-callback', (_, hashRoute) => {
  console.log('Auth0 callback received in preload:', hashRoute);
  // Dispatch a custom event that can be listened to in the React app
  document.dispatchEvent(new CustomEvent('auth0-callback-received', { detail: hashRoute }));
  
  // Also attempt to directly set the location hash
  if (window.location) {
    window.location.hash = hashRoute;
  }
});
