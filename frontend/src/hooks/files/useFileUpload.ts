import { useState, useCallback, useRef } from 'react';
import axios from 'axios';
import { v4 as uuidv4 } from 'uuid';
import useFileStore from '../../store/fileStore';
import { useEnhancedApi } from '../api';
import {
  FileLoadState,
  FileState,
  UploadProgress,
  UploadResult
} from './types';

/**
 * Hook for managing file uploads with progress tracking
 */
export const useFileUpload = () => {
  // State for upload operations
  const [state, setState] = useState<FileState>({
    loadState: FileLoadState.IDLE,
    error: null
  });

  // Track upload progress for each file
  const [uploadProgress, setUploadProgress] = useState<Record<string, UploadProgress>>({});

  // Get the enhanced API
  const { api } = useEnhancedApi();

  // Get file store actions
  const { addFile } = useFileStore();

  // Ref to store cancel tokens for each upload
  const cancelTokens = useRef<Record<string, any>>({});

  /**
   * Validate files before upload
   * @param files Files to validate
   * @returns Array of valid files
   */
  const validateFiles = useCallback((files: File[]): File[] => {
    const maxSize = 1024 * 1024 * 10; // 10MB max file size
    const validFiles = files.filter(file => {
      // Check file size
      if (file.size > maxSize) {
        console.warn(`File ${file.name} exceeds the maximum size of 10MB`);
        return false;
      }
      return true;
    });
    
    if (validFiles.length < files.length) {
      console.warn(`Some files were rejected due to size limitations`);
    }
    
    return validFiles;
  }, []);

  /**
   * Upload a single file with progress tracking
   * @param file File to upload
   * @param query_id Optional query ID for context
   * @param message_id Optional message ID for context
   * @returns Result of the upload operation
   */
  const uploadFile = useCallback(async (file: File, query_id?: string | null, message_id?: string | null): Promise<UploadResult> => {
    // Generate a unique ID for this upload
    const uploadId = `upload-${uuidv4()}`;

    // Create cancel token
    const cancelToken = axios.CancelToken.source();
    cancelTokens.current[uploadId] = cancelToken;

    // Initialize progress tracking
    setUploadProgress(prev => ({
      ...prev,
      [uploadId]: {
        id: uploadId,
        fileName: file.name,
        fileSize: file.size,
        progress: 0,
        status: 'pending'
      }
    }));

    setState({
      loadState: FileLoadState.LOADING,
      error: null
    });

    try {
      // Update status to uploading
      setUploadProgress(prev => ({
        ...prev,
        [uploadId]: { ...prev[uploadId], status: 'uploading' }
      }));

      // Define progress handler
      const onUploadProgress = (progressEvent: any) => {
        const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total);
        setUploadProgress(prev => ({
          ...prev,
          [uploadId]: { ...prev[uploadId], progress: percentCompleted }
        }));
      };

      // Perform upload
      const response = await api.uploadFileWithRetry(file, query_id, message_id, cancelToken.token, onUploadProgress);
      const fileData = response.data;

      // Transform API response to store format
      const newFile = {
        id: fileData.id,
        filename: fileData.filename,
        fileType: fileData.file_type,
        fileSize: fileData.file_size,
        storagePath: fileData.storage_path,
        createdAt: new Date(fileData.created_at),
        isProcessed: fileData.is_processed,
        isDeleted: fileData.is_deleted || false,
        metadata: fileData.metadata
      };

      // Add file to store
      addFile(newFile);

      // Update progress to 100% and status to success
      setUploadProgress(prev => ({
        ...prev,
        [uploadId]: { ...prev[uploadId], progress: 100, status: 'success' }
      }));

      setState({
        loadState: FileLoadState.LOADED,
        error: null
      });

      // Clean up
      delete cancelTokens.current[uploadId];

      // Remove progress tracking after a delay
      setTimeout(() => {
        setUploadProgress(prev => {
          const newProgress = { ...prev };
          delete newProgress[uploadId];
          return newProgress;
        });
      }, 2000);

      return { success: true, file: newFile };
    } catch (err) {
      // Check if the request was canceled
      if (axios.isCancel(err)) {
        console.log(`Upload of ${file.name} was canceled`);
        
        setUploadProgress(prev => ({
          ...prev,
          [uploadId]: { 
            ...prev[uploadId], 
            status: 'error',
            error: 'Upload canceled'
          }
        }));
        
        setState({
          loadState: FileLoadState.ERROR,
          error: 'Upload canceled'
        });
        
        return { success: false, file: null, error: 'Upload canceled' };
      }

      // Handle other errors
      const errorMessage = err instanceof Error ? err.message : `Failed to upload file ${file.name}`;
      console.error(errorMessage, err);

      setUploadProgress(prev => ({
        ...prev,
        [uploadId]: { 
          ...prev[uploadId], 
          status: 'error',
          error: errorMessage
        }
      }));

      setState({
        loadState: FileLoadState.ERROR,
        error: errorMessage
      });

      // Clean up
      delete cancelTokens.current[uploadId];

      // Remove progress tracking after a delay
      setTimeout(() => {
        setUploadProgress(prev => {
          const newProgress = { ...prev };
          delete newProgress[uploadId];
          return newProgress;
        });
      }, 5000);

      return { success: false, file: null, error: errorMessage };
    }
  }, [api, addFile]);

  /**
   * Upload multiple files
   * @param files Array of files to upload
   * @param query_id Optional query ID for context (applied to all files in batch)
   * @param message_id Optional message ID for context (applied to all files in batch)
   * @returns Array of upload results
   */
  const uploadFiles = useCallback(async (files: File[], query_id?: string | null, message_id?: string | null): Promise<UploadResult[]> => {
    setState({
      loadState: FileLoadState.LOADING,
      error: null
    });

    try {
      // Upload files in parallel
      const results = await Promise.all(
        files.map(file => uploadFile(file, query_id, message_id))
      );

      // If any uploads failed, set an error message
      const failedUploads = results.filter(result => !result.success);
      if (failedUploads.length > 0) {
        setState({
          loadState: FileLoadState.ERROR,
          error: `${failedUploads.length} of ${files.length} files failed to upload`
        });
      } else {
        setState({
          loadState: FileLoadState.LOADED,
          error: null
        });
      }

      return results;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to upload files';
      console.error(errorMessage, err);
      
      setState({
        loadState: FileLoadState.ERROR,
        error: errorMessage
      });
      
      return files.map(file => ({
        success: false,
        file: null,
        error: errorMessage
      }));
    }
  }, [uploadFile]);

  /**
   * Cancel an in-progress upload
   * @param uploadId ID of the upload to cancel
   */
  const cancelUpload = useCallback((uploadId: string) => {
    if (cancelTokens.current[uploadId]) {
      cancelTokens.current[uploadId].cancel('Upload canceled by user');
      delete cancelTokens.current[uploadId];

      setUploadProgress(prev => {
        const newProgress = { ...prev };
        
        if (newProgress[uploadId]) {
          newProgress[uploadId] = {
            ...newProgress[uploadId],
            status: 'error',
            error: 'Canceled by user'
          };
        }
        
        return newProgress;
      });

      // Remove from progress tracking after a delay
      setTimeout(() => {
        setUploadProgress(prev => {
          const newProgress = { ...prev };
          delete newProgress[uploadId];
          return newProgress;
        });
      }, 2000);
    }
  }, []);

  /**
   * Cancel all in-progress uploads
   */
  const cancelAllUploads = useCallback(() => {
    // Cancel each upload
    Object.keys(cancelTokens.current).forEach(uploadId => {
      cancelTokens.current[uploadId].cancel('All uploads canceled by user');
      delete cancelTokens.current[uploadId];
    });

    // Update progress for all uploads
    setUploadProgress(prev => {
      const newProgress: Record<string, UploadProgress> = {};
      
      // Mark all as canceled
      Object.keys(prev).forEach(uploadId => {
        newProgress[uploadId] = {
          ...prev[uploadId],
          status: 'error',
          error: 'Canceled by user'
        };
      });
      
      return newProgress;
    });

    // Clear progress after delay
    setTimeout(() => {
      setUploadProgress({});
    }, 2000);
  }, []);

  return {
    uploadFile,
    uploadFiles,
    cancelUpload,
    cancelAllUploads,
    validateFiles,
    uploadProgress: Object.values(uploadProgress),
    isUploading: state.loadState === FileLoadState.LOADING,
    error: state.error
  };
};

export default useFileUpload; 