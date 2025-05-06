export {};

declare global {
  interface Window {
    /**
     * Function to reset circuit breaker for the network
     */
    resetCircuitBreaker?: () => void;
    
    /**
     * Function to reset message loading state
     */
    resetMessageLoadingState?: () => void;
    
    /**
     * Electron API for the application
     */
    electron?: {
      // Window management
      openMainWindow: () => Promise<void>;
      closeSubWindow: () => Promise<void>;
      minimizeMainWindow: () => Promise<void>;
      
      // API configuration
      getApiUrl: () => Promise<string>;
      getApiKey: () => Promise<string>;
      
      // Data capture
      waitForCaptureData: () => Promise<any>;
      
      // API response handling
      waitForApiResponse: () => Promise<any>;
      waitForApiError: () => Promise<any>;
      
      // Loading state
      onApiLoadingChange: (callback: (isLoading: boolean) => void) => (() => void);
      
      // Option selection
      sendSelectedOption: (option: any) => Promise<void>;
      onSelectedOption: (callback: (option: any) => void) => (() => void);
      
      // Screenshot and text capture
      getSelectedText: () => Promise<string>;
      captureScreenshot: () => Promise<string>;
    };
  }
} 