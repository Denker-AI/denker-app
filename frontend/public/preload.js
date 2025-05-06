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

contextBridge.exposeInMainWorld(
  'electron',
  {
    // Window management
    openMainWindow: () => ipcRenderer.invoke('open-main-window'),
    closeSubWindow: () => ipcRenderer.invoke('close-sub-window'),
    minimizeMainWindow: () => ipcRenderer.invoke('minimize-main-window'),
    
    // API configuration
    getApiUrl: () => ipcRenderer.invoke('get-api-url'),
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
  }
);
