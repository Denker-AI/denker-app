// Ensure this file is treated as a module if it doesn't have any top-level imports or exports.
// Adding an empty export can achieve this, but usually not needed for .d.ts files meant for global augmentation.
export {}; // Uncomment if you face issues with this file not being treated as a module and global augmentation not applying.

import type { CaptureData } from './types/types'; // Assuming CaptureData is in types.ts and types.ts is correctly pathed

// This is the interface that will be available on window.electron
interface DenkerElectronAPI {
  getEnvVars: () => {
    VITE_API_URL?: string;
    VITE_WS_URL?: string;
    VITE_AUTH0_DOMAIN?: string;
    VITE_AUTH0_CLIENT_ID?: string;
    VITE_AUTH0_AUDIENCE?: string;
    VITE_NODE_ENV?: string;
    NODE_ENV?: string;
    [key: string]: string | undefined;
  };
  getApiUrl: () => string; // This was in your previous version, ensure it's exposed in preload if used
  getApiKey: () => Promise<string>;
  openMainWindow: () => Promise<void>;
  closeSubWindow: () => Promise<void>;
  minimizeMainWindow: () => Promise<void>;
  
  waitForCaptureData: () => Promise<CaptureData>;
  toggleTransparency: (isTransparent: boolean) => Promise<boolean>;
  
  // Auth0 related functions from preload
  onAuth0Callback: (callback: (hashRoute: string) => void) => void; // From your previous version
  onDeepLink: (callback: (url: string) => void) => void; // From your previous version
  
  // File system operations
  openFile: (filePath?: string) => Promise<{ success: boolean; error?: string } | string>;
  openDirectoryDialog: () => Promise<string | null>; // The problematic one
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
  
  // Auth0 specific methods exposed in preload.js
  login?: () => Promise<any>;
  getAccessToken?: () => Promise<string | null>;
  logout?: () => Promise<any>;
  
  // Onboarding
  onShowOnboarding?: (callback: () => void) => () => void;
  getUserInfo?: () => Promise<any>;
  onAuthSuccessful?: (callback: () => void) => (() => void) | undefined;
  onAuthFailed?: (callback: (errorInfo: any) => void) => (() => void) | undefined;
  onAuthLoggedOut?: (callback: () => void) => (() => void) | undefined;
  devProcessAuth0Callback: (params: { code: string; state: string }) => Promise<{ success: boolean; error?: string }>;

  // Other methods from preload that could be added if needed by renderer
  sendSelectedOption?: (option: any) => Promise<any>;
  onSelectedOption?: (callback: (option: any) => void) => (() => void) | undefined;
  getSelectedText?: () => Promise<string>;
  captureScreenshot?: () => Promise<any>;

  // App control
  restartApp: () => Promise<void>;
  requestLocalBackendRestart: () => Promise<{success: boolean, message: string}>;
  showRestartDialog: (options?: {
    title?: string;
    message?: string;
    detail?: string;
  }) => Promise<{ response: number }>;
}

declare global {
  interface Window {
    electron: DenkerElectronAPI;
    // Potentially other global properties your app might set on window
    // Example: electronIsPreloadedByScript?: boolean;
  }
} 