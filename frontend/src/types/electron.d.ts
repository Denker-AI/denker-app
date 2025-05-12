import type { CaptureData } from './types';

declare global {
  interface Window {
    electron: {
      waitForCaptureData: () => Promise<CaptureData>;
      openMainWindow: () => void;
      closeSubWindow: () => void;
      minimizeMainWindow: () => void;
      toggleTransparency: (isTransparent: boolean) => Promise<boolean>;
    }
  }
} 