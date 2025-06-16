// Original captured data from user (clipboard + screenshot)
export interface CaptureData {
  text: string;
  screenshot: string | null;
  mode: 'text' | 'screenshot' | 'both' | 'error';
  timestamp: number;  // When the data was captured
  clipboardAge: number;  // How old the clipboard content is
  metadata: {
    captureTime: number;  // When the capture was initiated
  };
}

export interface Option {
  id: string;
  title: string;
  description: string;
}

// API request format for intention agent
export interface IntentionRequest {
  query_id: string;
  text: string | null;
  screenshot: string | null;
  screenshot_mime_type?: string;
  mode: 'text' | 'screenshot' | 'both' | 'error';
}

// API response format from intention agent
export interface IntentionResponse {
  query_id: string;
  options: Option[];
  error?: string;
}

// Combined data for subwindow (original capture + API response)
export interface CaptureDataWithResponse extends CaptureData {
  apiResponse: IntentionResponse;
}

export interface ElectronAPI {
  waitForCaptureData: () => Promise<CaptureData>;
  waitForApiResponse: () => Promise<IntentionResponse>;
  waitForApiError: () => Promise<string>;
  onApiLoadingChange: (callback: (isLoading: boolean) => void) => () => void;
  sendSelectedOption: (option: Option) => Promise<boolean>;
  onSelectedOption: (callback: (option: Option) => void) => () => void;
  openMainWindow: () => Promise<void>;
  closeSubWindow: () => Promise<void>;
  minimizeMainWindow: () => Promise<void>;
  getSelectedText: () => Promise<string>;
  captureScreenshot: () => Promise<string>;
  getApiUrl: () => Promise<string>;
  getApiKey: () => Promise<string>;
  platform: string;
  onWindowClose: (callback: () => void) => () => void;
  onWindowMinimize: (callback: () => void) => () => void;
  onWindowMaximize: (callback: () => void) => () => void;
  onWindowUnmaximize: (callback: () => void) => () => void;
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
  openFile: () => Promise<string>;
  showDenkerFolder: () => Promise<void>;
  downloadFile: (fileId: string) => Promise<void>;
  writeToClipboard: (text: string) => Promise<void>;
  readFromClipboard: () => Promise<string>;
  minimizeToSystemTray: () => Promise<void>;
  toggleAlwaysOnTop: () => Promise<void>;
  exitApp: () => Promise<void>;
  onAuth0Callback: (callback: (hashRoute: string) => void) => void;
  onDeepLink: (callback: (url: string) => void) => void;
}

declare global {
  interface Window {
    electron: ElectronAPI;
  }
}

export interface Message {
  id: string;
  content: string | any;
  role: 'user' | 'assistant' | 'system';
  timestamp: Date;
  files?: FileAttachment[];
  metadata?: Record<string, any>;
  type?: 'thinking' | 'tool_call' | 'result' | 'synthesis';
  tool?: {
    name: string;
    query: string;
  };
  source?: 'document' | 'web';
} 