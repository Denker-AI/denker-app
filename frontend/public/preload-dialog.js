const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronDialog', {
  sendResponse: (action) => ipcRenderer.send('custom-restart-dialog-response', action),
  getDialogOptions: () => {
    const params = new URLSearchParams(window.location.search);
    return {
      title: params.get('title'),
      message: params.get('message'),
      detail: params.get('detail'),
    };
  }
}); 