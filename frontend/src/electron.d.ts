import { ElectronAPI } from './types/types';

interface ElectronAPI {
  getEnvVars: () => {
    VITE_API_URL: string;
    VITE_WS_URL: string;
    [key: string]: string;
  };
  getApiUrl: () => string;
  getApiKey: () => Promise<string>;
  openMainWindow: () => Promise<void>;
  closeSubWindow: () => Promise<void>;
  minimizeMainWindow: () => Promise<void>;
  
  // Auth0 related functions
  onAuth0Callback: (callback: (hashRoute: string) => void) => void;
  onDeepLink: (callback: (url: string) => void) => void;
  
  // File system operations
  openFile: () => Promise<string>;
  showDenkerFolder: () => Promise<void>;
  downloadFile: (fileId: string) => Promise<void>;
  
  // Clipboard operations
  writeToClipboard: (text: string) => Promise<void>;
  readFromClipboard: () => Promise<string>;
  
  // Window operations
  minimizeToSystemTray: () => Promise<void>;
  toggleAlwaysOnTop: () => Promise<void>;
  
  // General utilities
  exitApp: () => Promise<void>;
  
  // Add other methods as needed
}

declare global {
  interface Window {
    electron: ElectronAPI;
  }
} 