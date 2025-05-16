import { useState, useCallback, useEffect } from 'react';
import useFileStore from '../../store/fileStore';
import { useEnhancedApi } from '../api';
import {
  FileLoadState,
  FileState,
  FileListItem
} from './types';

/**
 * Hook for managing file listings and selection
 */
export const useFileListing = () => {
  // State for file listing operations
  const [state, setState] = useState<FileState>({
    loadState: FileLoadState.IDLE,
    error: null
  });

  // Get the enhanced API
  const { api } = useEnhancedApi();

  // Get file store state and actions
  const {
    files,
    setFiles,
    selectedFileIds,
    selectFile,
    deselectFile,
    toggleFileSelection,
    clearSelection,
    getSelectedFiles
  } = useFileStore();

  // Track initialization state to avoid redundant loading
  const [isInitialized, setIsInitialized] = useState(false);

  /**
   * Load files from API
   * @returns Array of files
   */
  const loadFiles = useCallback(async () => {
    console.log('[useFileListing] loadFiles called. Current loadState:', state.loadState);
    // Skip loading if already in progress
    if (state.loadState === FileLoadState.LOADING) {
      return files;
    }

    setState({
      loadState: FileLoadState.LOADING,
      error: null
    });

    try {
      const filesArray = await api.getFilesWithRetry();
      
      // Transform API response to match store format
      const filesData = filesArray.map((file: any) => ({
        id: file.id,
        filename: file.filename,
        fileType: file.file_type,
        fileSize: file.file_size,
        storagePath: file.storage_path,
        createdAt: new Date(file.created_at),
        isProcessed: file.is_processed,
        isDeleted: file.is_deleted || false,
        metadata: file.metadata
      }));
      
      setFiles(filesData);
      setIsInitialized(true);
      
      setState({
        loadState: FileLoadState.LOADED,
        error: null
      });
      
      return filesData;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to load files';
      console.error('Error loading files:', errorMessage);
      
      setState({
        loadState: FileLoadState.ERROR,
        error: errorMessage
      });
      
      return [];
    }
  }, [api, files, setFiles, state.loadState]);

  // Load files on mount if not already initialized
  useEffect(() => {
    console.log('[useFileListing] Mount effect. isInitialized:', isInitialized);
    if (!isInitialized) {
      console.log('[useFileListing] Mount effect: Calling loadFiles.');
      loadFiles();
    }
  }, [isInitialized, loadFiles]);

  /**
   * Refresh files periodically
   */
  useEffect(() => {
    // Skip if not initialized
    if (!isInitialized) return;
    console.log('[useFileListing] Refresh interval setup.');

    // Refresh every 30 seconds
    const intervalId = setInterval(() => {
      console.log('[useFileListing] Interval: Calling loadFiles.');
      loadFiles().catch(err => {
        console.error('Error refreshing files:', err);
      });
    }, 30000);

    return () => clearInterval(intervalId);
  }, [isInitialized, loadFiles]);

  /**
   * Listen for file state changes from other components
   */
  useEffect(() => {
    const handleFileStateChanged = (event: CustomEvent) => {
      const { fileId, isDeleted } = event.detail;
      
      // Find the file in our list
      const fileIndex = files.findIndex(f => f.id === fileId);
      if (fileIndex >= 0) {
        // Create a new array to trigger state updates
        const updatedFiles = [...files];
        updatedFiles[fileIndex] = {
          ...updatedFiles[fileIndex],
          isDeleted: isDeleted
        };
        
        setFiles(updatedFiles);
        
        // If file is deleted and was selected, deselect it
        if (isDeleted && selectedFileIds.includes(fileId)) {
          deselectFile(fileId);
        }
      }
    };

    // Add event listener
    window.addEventListener('file-state-changed', handleFileStateChanged as EventListener);

    // Clean up
    return () => {
      window.removeEventListener('file-state-changed', handleFileStateChanged as EventListener);
    };
  }, [files, setFiles, selectedFileIds, deselectFile]);

  /**
   * Filter files that are not deleted
   */
  const activeFiles = files.filter(file => !file.isDeleted);

  /**
   * Transform files for UI display
   */
  const fileList: FileListItem[] = activeFiles.map(file => ({
    ...file,
    isSelected: selectedFileIds.includes(file.id)
  }));

  /**
   * Get selected files
   */
  const selectedFiles = getSelectedFiles();

  return {
    files: fileList,
    selectedFiles,
    selectedFileIds,
    isLoading: state.loadState === FileLoadState.LOADING,
    isError: state.loadState === FileLoadState.ERROR,
    error: state.error,
    isInitialized,
    
    // Actions
    loadFiles,
    selectFile,
    deselectFile,
    toggleFileSelection,
    clearSelection
  };
};

export default useFileListing; 