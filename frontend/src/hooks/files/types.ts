import { FileItem } from '../../store/fileStore';

/**
 * File loading states
 */
export enum FileLoadState {
  /** Not loading anything */
  IDLE = 'idle',
  /** Loading in progress */
  LOADING = 'loading',
  /** Successfully loaded */
  LOADED = 'loaded',
  /** Error occurred */
  ERROR = 'error'
}

/**
 * Common state interface for file operations
 */
export interface FileState {
  /** Loading state */
  loadState: FileLoadState;
  /** Error message if any */
  error: string | null;
}

/**
 * Upload progress tracking
 */
export interface UploadProgress {
  /** File ID or temporary ID during upload */
  id: string;
  /** Upload progress percentage (0-100) */
  progress: number;
  /** Current status of the upload */
  status: 'pending' | 'uploading' | 'success' | 'error';
  /** File name being uploaded */
  fileName: string;
  /** Size of the file in bytes */
  fileSize?: number;
  /** Error message if status is 'error' */
  error?: string;
}

/**
 * Result of a file upload operation
 */
export interface UploadResult {
  /** Whether the upload was successful */
  success: boolean;
  /** The uploaded file if successful */
  file: FileItem | null;
  /** Error message if any */
  error?: string;
}

/**
 * Result of a file download operation
 */
export interface DownloadResult {
  /** Whether the download was successful */
  success: boolean;
  /** File ID */
  fileId: string;
  /** Local path or URL if download was successful */
  path?: string;
  /** Error message if any */
  error?: string;
}

/**
 * File item with additional UI state
 */
export interface FileListItem extends FileItem {
  /** Whether the file is currently selected */
  isSelected?: boolean;
  /** Whether the file is currently being downloaded */
  isDownloading?: boolean;
  /** Whether the file is currently being deleted */
  isDeleting?: boolean;
}

/**
 * Type exported for compatibility
 */
export type { FileItem }; 