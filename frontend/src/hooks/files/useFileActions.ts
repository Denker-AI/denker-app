import { useState, useCallback } from 'react';
import useFileStore from '../../store/fileStore';
import { useEnhancedApi } from '../api';
import {
  FileLoadState,
  FileState,
  DownloadResult
} from './types';

/**
 * Hook for file actions like downloading and deleting files
 */
export const useFileActions = () => {
  // State for file operations
  const [state, setState] = useState<FileState>({
    loadState: FileLoadState.IDLE,
    error: null
  });

  // Track files currently being processed
  const [processingFiles, setProcessingFiles] = useState<Record<string, string>>({});

  // Get the enhanced API
  const { api } = useEnhancedApi();

  // Get file store actions
  const { updateFile } = useFileStore();

  /**
   * Check if a file exists and is not deleted
   * @param fileId ID of the file to check
   * @returns Boolean indicating if file is available
   */
  const checkFileStatus = useCallback(async (fileId: string): Promise<boolean> => {
    try {
      const response = await api.getFileWithRetry(fileId);
      const fileData = response.data;
      
      // If the file exists in the API but is marked as deleted, update local store
      if (fileData.is_deleted) {
        updateFile(fileId, { isDeleted: true });
        return false;
      }
      
      return true;
    } catch (error) {
      console.error(`Error checking file status for ${fileId}:`, error);
      
      // If file not found on server, mark as deleted locally
      if (error.response?.status === 404) {
        updateFile(fileId, { isDeleted: true });
      }
      
      return false;
    }
  }, [api, updateFile]);

  /**
   * Download a file
   * @param fileId ID of the file to download
   * @returns Result of the download operation
   */
  const downloadFile = useCallback(async (fileId: string): Promise<DownloadResult> => {
    if (!fileId) {
      return {
        success: false,
        fileId,
        error: 'No file ID provided'
      };
    }

    // Check if already processing this file
    if (processingFiles[fileId] === 'downloading') {
      return {
        success: false,
        fileId,
        error: 'File is already being downloaded'
      };
    }

    // Mark file as being downloaded
    setProcessingFiles(prev => ({
      ...prev,
      [fileId]: 'downloading'
    }));

    setState({
      loadState: FileLoadState.LOADING,
      error: null
    });

    try {
      // Check file status first
      const isAvailable = await checkFileStatus(fileId);
      if (!isAvailable) {
        setState({
          loadState: FileLoadState.ERROR,
          error: 'This file has been deleted and is no longer available'
        });
        
        setProcessingFiles(prev => {
          const newState = { ...prev };
          delete newState[fileId];
          return newState;
        });
        
        return {
          success: false,
          fileId,
          error: 'This file has been deleted and is no longer available'
        };
      }

      // Download the file
      const result = await api.downloadFile(fileId);
      
      setState({
        loadState: FileLoadState.IDLE,
        error: null
      });
      
      // Clear processing state
      setProcessingFiles(prev => {
        const newState = { ...prev };
        delete newState[fileId];
        return newState;
      });

      if (!result.success) {
        const errorMessage = result.error || 'Failed to download file';
        
        setState({
          loadState: FileLoadState.ERROR,
          error: errorMessage
        });
        
        // If file not found or deleted, update local state
        if (result.error === 'File not found' || result.error === 'File has been deleted') {
          updateFile(fileId, { isDeleted: true });
        }
        
        return {
          success: false,
          fileId,
          error: errorMessage
        };
      }

      return {
        success: true,
        fileId,
        path: result.path
      };
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'An unexpected error occurred';
      console.error('Error in downloadFile function:', error);
      
      setState({
        loadState: FileLoadState.ERROR,
        error: errorMessage
      });
      
      // Clear processing state
      setProcessingFiles(prev => {
        const newState = { ...prev };
        delete newState[fileId];
        return newState;
      });
      
      return {
        success: false,
        fileId,
        error: errorMessage
      };
    }
  }, [api, checkFileStatus, processingFiles, updateFile]);

  /**
   * Delete a file
   * @param fileId ID of the file to delete
   * @returns Whether deletion was successful
   */
  const deleteFile = useCallback(async (fileId: string): Promise<boolean> => {
    if (!fileId) {
      setState({
        loadState: FileLoadState.ERROR,
        error: 'No file ID provided'
      });
      return false;
    }

    // Check if already processing this file
    if (processingFiles[fileId] === 'deleting') {
      return false;
    }

    // Mark file as being deleted
    setProcessingFiles(prev => ({
      ...prev,
      [fileId]: 'deleting'
    }));

    setState({
      loadState: FileLoadState.LOADING,
      error: null
    });

    try {
      // Delete from API
      const response = await api.deleteFileWithRetry(fileId);
      
      // Update local store to mark as deleted
      updateFile(fileId, { isDeleted: true });
      
      // Dispatch event to notify other components
      window.dispatchEvent(new CustomEvent('file-state-changed', { 
        detail: { fileId, isDeleted: true } 
      }));
      
      setState({
        loadState: FileLoadState.IDLE,
        error: null
      });
      
      // Clear processing state
      setProcessingFiles(prev => {
        const newState = { ...prev };
        delete newState[fileId];
        return newState;
      });
      
      return true;
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to delete file';
      console.error('Error deleting file:', errorMessage);
      
      setState({
        loadState: FileLoadState.ERROR,
        error: errorMessage
      });
      
      // If file doesn't exist in backend, still mark as deleted locally
      if (error.response?.status === 404) {
        updateFile(fileId, { isDeleted: true });
        
        // Dispatch event to notify other components
        window.dispatchEvent(new CustomEvent('file-state-changed', { 
          detail: { fileId, isDeleted: true } 
        }));
      }
      
      // Clear processing state
      setProcessingFiles(prev => {
        const newState = { ...prev };
        delete newState[fileId];
        return newState;
      });
      
      return false;
    }
  }, [api, processingFiles, updateFile]);

  return {
    downloadFile,
    deleteFile,
    checkFileStatus,
    isLoading: state.loadState === FileLoadState.LOADING,
    error: state.error,
    processingFiles
  };
};

export default useFileActions; 