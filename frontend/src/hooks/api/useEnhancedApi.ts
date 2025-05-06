import { useMemo, useCallback } from 'react';
import { useApi } from '../../services/api';
import { useRetryLogic } from './useRetryLogic';
import { useApiStatus, ApiStatus } from './useApiStatus';
import axios, { AxiosError } from 'axios';

/**
 * Network error types categorization
 */
export enum NetworkErrorType {
  /** Server returned an error response */
  SERVER_ERROR = 'server_error',
  /** No response from server - network connectivity issue */
  NETWORK_ERROR = 'network_error',
  /** Request was canceled by user or timeout */
  CANCELED = 'canceled',
  /** Unknown error */
  UNKNOWN = 'unknown'
}

/**
 * Enhanced API hook that adds retry logic and circuit breaker pattern
 * to the base API service.
 */
export const useEnhancedApi = () => {
  // Get the base API service
  const api = useApi();
  
  // Get retry logic
  const { executeWithRetry } = useRetryLogic();
  
  // Get circuit breaker status and methods
  const {
    apiStatus,
    shouldAllowRequest,
    recordSuccess,
    recordFailure,
    resetCircuitBreaker
  } = useApiStatus();

  /**
   * Categorize errors to handle them appropriately
   * @param error - The error to categorize
   * @returns The type of network error
   */
  const categorizeError = useCallback((error: any): NetworkErrorType => {
    if (axios.isAxiosError(error)) {
      const axiosError = error as AxiosError;
      
      // Check if the request was canceled
      if (axiosError.code === 'ERR_CANCELED') {
        return NetworkErrorType.CANCELED;
      }
      
      // Check if there was a response from server
      if (axiosError.response) {
        return NetworkErrorType.SERVER_ERROR;
      }
      
      // No response - network error
      if (axiosError.request) {
        return NetworkErrorType.NETWORK_ERROR;
      }
    }
    
    return NetworkErrorType.UNKNOWN;
  }, []);

  /**
   * Enhanced version of API calls with retry logic and circuit breaker
   * @param apiMethod - The API method to call
   * @param shouldRetry - Whether to retry on failure
   * @returns Promise with the API result
   */
  const callWithRetry = useCallback(
    async <T, Args extends any[]>(
      apiMethod: (...args: Args) => Promise<T>,
      args: Args,
      shouldRetry = true,
      maxAttempts = 3
    ): Promise<T> => {
      let attempts = 0;

      // Check if circuit breaker allows request
      if (!shouldAllowRequest()) {
        throw new Error('API circuit breaker is open - too many recent failures');
      }

      try {
        // Create a function that calls the API method with the provided arguments
        const apiCall = async () => {
          attempts++;
          if (attempts > maxAttempts) {
            throw new Error(`Maximum attempts (${maxAttempts}) reached`);
          }
          return apiMethod(...args);
        };
        
        // Execute with retry if requested, or directly if not
        const result = shouldRetry 
          ? await executeWithRetry(apiCall, { maxRetries: maxAttempts - 1 })
          : await apiCall();
        
        // Record success for circuit breaker
        recordSuccess();
        
        return result;
      } catch (error) {
        // Categorize the error
        const errorType = categorizeError(error);
        
        // Only record certain types of errors for circuit breaker
        if (errorType === NetworkErrorType.NETWORK_ERROR) {
          console.error('Network error in API call:', error);
          recordFailure();
        } else if (errorType === NetworkErrorType.SERVER_ERROR) {
          const axiosError = error as AxiosError;
          if (axiosError.response?.status === 500) {
            console.error('Server error in API call:', error);
            recordFailure();
          }
        }
        
        throw error;
      }
    },
    [shouldAllowRequest, executeWithRetry, recordSuccess, recordFailure, categorizeError]
  );

  // Create enhanced API methods
  const enhancedApi = useMemo(() => {
    // Create a new object to avoid mutating the original API
    return {
      // Expose original API methods
      ...api,
      
      // Add enhanced versions
      getConversationsWithRetry: (shouldRetry = true) => 
        callWithRetry(api.getConversations, [], shouldRetry),
      
      // Update getConversationWithRetry to accept and pass pagination params
      getConversationWithRetry: (id: string, params?: { limit?: number; before_message_id?: string }, shouldRetry = true) => 
        callWithRetry(api.getConversation, [id, params], shouldRetry),
      
      createConversationWithRetry: (data: any, shouldRetry = true) => 
        callWithRetry(api.createConversation, [data], shouldRetry),
      
      updateConversationWithRetry: (id: string, data: any, shouldRetry = true) => 
        callWithRetry(api.updateConversation, [id, data], shouldRetry),
      
      deleteConversationWithRetry: (id: string, shouldRetry = true) => {
        console.log('Enhanced API: Calling deleteConversationWithRetry for ID:', id);
        return callWithRetry(api.deleteConversation, [id], shouldRetry)
          .then(result => {
            console.log('Enhanced API: deleteConversation succeeded with result:', result);
            return result;
          })
          .catch(error => {
            console.error('Enhanced API: deleteConversation failed with error:', error);
            throw error;
          });
      },
      
      addMessageWithRetry: (conversationId: string, data: any, shouldRetry = true) => 
        callWithRetry(api.addMessage, [conversationId, data], shouldRetry),
      
      // Add sendMessageWithRetry method
      sendMessageWithRetry: (text: string, conversationId: string, attachments: any[] = [], shouldRetry = true) => 
        callWithRetry(api.sendMessage, [text, conversationId, attachments], shouldRetry),
      
      // File operations
      getFilesWithRetry: (shouldRetry = true) => 
        callWithRetry(api.getFiles, [], shouldRetry),
      
      getFileWithRetry: (id: string, shouldRetry = true) => 
        callWithRetry(api.getFile, [id], shouldRetry),
      
      uploadFileWithRetry: (file: File, query_id?: string | null, message_id?: string | null, cancelToken?: any, onUploadProgress?: any, shouldRetry = false) => 
        callWithRetry(api.uploadFile, [file, query_id, message_id, cancelToken, onUploadProgress], shouldRetry),
      
      deleteFileWithRetry: (id: string, shouldRetry = true) => 
        callWithRetry(api.deleteFile, [id], shouldRetry),
      
      // Add method to reset circuit breaker
      resetNetworkStatus: resetCircuitBreaker,

      // --- ADDED: Expose coordinator status check with retry --- 
      checkCoordinatorStatusWithRetry: (queryId: string, shouldRetry = true) => 
        callWithRetry(api.checkCoordinatorStatus, [queryId], shouldRetry),
      // --- END ADDED ---

      // --- ADDED: Expose coordinator processing with retry (optional, adjust retry as needed) ---
      processMCPCoordinatorWithRetry: (data: any, shouldRetry = false) => // Defaulting retry to false for long-running process
        callWithRetry(api.processMCPCoordinator, [data], shouldRetry),
      // --- END ADDED ---
    };
  }, [api, callWithRetry, resetCircuitBreaker]);

  return {
    api: enhancedApi,
    apiStatus,
    isOnline: apiStatus === ApiStatus.ONLINE,
    isDegraded: apiStatus === ApiStatus.DEGRADED,
    isOffline: apiStatus === ApiStatus.OFFLINE
  };
};

export default useEnhancedApi; 