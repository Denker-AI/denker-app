import { ElectronAPI } from './types/types';

declare global {
  interface Window {
    electron: ElectronAPI;
  }
} 