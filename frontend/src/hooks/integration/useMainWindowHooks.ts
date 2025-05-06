import { useMemo } from 'react';
import { useConversationList, useCurrentConversation, useMessageSender, useRealTimeUpdates } from '../conversation';
import { useFileUpload, useFileActions, useFileListing } from '../files';
import { useEnhancedApi } from '../api';

/**
 * Integrated hook that combines all hooks needed for the MainWindow component.
 * This provides a simpler API for the component to use.
 */
export const useMainWindowHooks = () => {
  // API hooks
  const { apiStatus, isOnline, isDegraded, isOffline } = useEnhancedApi();
  
  // Conversation hooks
  const conversationList = useConversationList();
  const currentConversation = useCurrentConversation();
  const messageSender = useMessageSender();
  const realTimeUpdates = useRealTimeUpdates();
  
  // File hooks
  const fileUpload = useFileUpload();
  const fileActions = useFileActions();
  const fileListing = useFileListing();

  // Memoize the conversation API to avoid unnecessary re-renders
  const conversationAPI = useMemo(() => ({
    // Current conversation data
    currentConversation: currentConversation.currentConversation,
    loadState: currentConversation.loadState,
    isLoadingConversation: currentConversation.isLoading,
    isConversationError: currentConversation.isError,
    conversationError: currentConversation.error,
    
    // Conversation list data
    conversationList: conversationList.conversationList,
    isLoadingConversationList: conversationList.isLoading,
    conversationListError: conversationList.error,
    currentConversationId: conversationList.currentConversationId,
    
    // Message sending status
    isSendingMessage: messageSender.isLoading,
    showLoadingIndicator: messageSender.showLoading,
    messageSendingError: messageSender.error,
    
    // WebSocket status
    isWebSocketConnected: realTimeUpdates.isConnected,
    
    // Combined loading state
    isLoading: currentConversation.isLoading || 
               conversationList.isLoading || 
               messageSender.showLoading,
    
    // Actions
    loadConversation: currentConversation.loadConversation,
    loadConversations: conversationList.loadConversations,
    createConversation: conversationList.createConversation,
    deleteConversation: conversationList.deleteConversation,
    deleteAllConversations: conversationList.deleteAllConversations,
    setCurrentConversationId: conversationList.setCurrentConversationId,
    sendMessage: messageSender.sendMessage,
    updateTitle: currentConversation.updateTitle,
    handleCoordinatorResponse: realTimeUpdates.handleCoordinatorResponse,
    connectToWebSocket: realTimeUpdates.connectToWebSocket,
    clearLoadedConversationsCache: currentConversation.clearLoadedConversationsCache,
    
    // Additional helpers from store that are passed through
    addMessage: currentConversation.addMessage,
    updateMessage: currentConversation.updateMessage,
    
    // Pagination related state and functions from useCurrentConversation
    isLoadingMore: currentConversation.isLoadingMore,
    hasMoreMessages: currentConversation.hasMoreMessages,
    loadMoreMessages: currentConversation.loadMoreMessages,
    prependMessages: currentConversation.prependMessages,
    setConversationPagination: currentConversation.setConversationPagination
  }), [
    currentConversation,
    conversationList,
    messageSender,
    realTimeUpdates
  ]);

  // Memoize the file API to avoid unnecessary re-renders
  const fileAPI = useMemo(() => ({
    // File listing data
    files: fileListing.files,
    selectedFiles: fileListing.selectedFiles,
    selectedFileIds: fileListing.selectedFileIds,
    isLoadingFiles: fileListing.isLoading,
    fileListError: fileListing.error,
    
    // File upload data
    isUploading: fileUpload.isUploading,
    uploadProgress: fileUpload.uploadProgress,
    uploadError: fileUpload.error,
    
    // File actions data
    isProcessingFile: fileActions.isLoading,
    processingFiles: fileActions.processingFiles,
    fileActionError: fileActions.error,
    
    // Combined loading state
    isLoading: fileListing.isLoading || 
               fileUpload.isUploading || 
               fileActions.isLoading,
    
    // Actions
    loadFiles: fileListing.loadFiles,
    uploadFile: fileUpload.uploadFile,
    uploadFiles: fileUpload.uploadFiles,
    validateFiles: fileUpload.validateFiles,
    cancelUpload: fileUpload.cancelUpload,
    cancelAllUploads: fileUpload.cancelAllUploads,
    downloadFile: fileActions.downloadFile,
    deleteFile: fileActions.deleteFile,
    checkFileStatus: fileActions.checkFileStatus,
    
    // Selection actions
    selectFile: fileListing.selectFile,
    deselectFile: fileListing.deselectFile,
    toggleFileSelection: fileListing.toggleFileSelection,
    clearSelection: fileListing.clearSelection
  }), [
    fileListing,
    fileUpload,
    fileActions
  ]);

  // Network status
  const networkAPI = useMemo(() => ({
    apiStatus,
    isOnline,
    isDegraded,
    isOffline
  }), [apiStatus, isOnline, isDegraded, isOffline]);

  return {
    conversation: conversationAPI,
    file: fileAPI,
    network: networkAPI
  };
};

export default useMainWindowHooks; 