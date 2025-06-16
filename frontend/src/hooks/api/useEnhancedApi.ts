import { useMemo, useCallback } from 'react';
import { api } from '../../services/api';
import { useRetryLogic } from './useRetryLogic';
import { useApiStatus, ApiStatus } from './useApiStatus';

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
    if (error instanceof TypeError && error.message && error.message.match(/network|fetch/i)) {
      return NetworkErrorType.NETWORK_ERROR;
    }
    if (error instanceof Error && error.message && error.message.match(/canceled|cancelled|aborted/i)) {
      return NetworkErrorType.CANCELED;
    }
    if (error instanceof Error && error.message && error.message.match(/api error|server error|500|502|503|504/i)) {
      return NetworkErrorType.SERVER_ERROR;
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
          console.error('Server error in API call:', error);
          recordFailure();
        }
        throw error;
      }
    },
    [shouldAllowRequest, executeWithRetry, recordSuccess, recordFailure, categorizeError]
  );

  // Create enhanced API methods
  const enhancedApi = useMemo(() => {
    return {
      // Expose original API methods
      ...api,
      // Add enhanced versions
      getConversationsWithRetry: (shouldRetry = true) => 
        callWithRetry(api.getConversations, [], shouldRetry),
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
      sendMessageWithRetry: (text: string, conversationId: string, attachments: any[] = [], shouldRetry = true) => 
        callWithRetry(api.sendMessage, [text, conversationId, attachments], shouldRetry),
      // Coordinator endpoints
      processMCPCoordinatorWithRetry: (data: any, shouldRetry = false) => 
        callWithRetry(api.processMCPCoordinator, [data], shouldRetry),
      checkCoordinatorStatusWithRetry: (queryId: string, shouldRetry = true) => 
        callWithRetry(api.checkCoordinatorStatus, [queryId], shouldRetry),
      // File endpoints
      uploadFileWithRetry: (file: File, additionalData: { user_id?: string | null, query_id?: string, message_id?: string, token?: string | null } = {}, shouldRetry = false) => 
        callWithRetry(api.uploadFile, [file, additionalData], shouldRetry),
      getFilesWithRetry: (params?: any, shouldRetry = true) =>
        callWithRetry(api.getFiles, [params], shouldRetry),
      getFileWithRetry: (fileId: string, shouldRetry = true) =>
        callWithRetry(api.get, [`/files/${fileId}`], shouldRetry),
      downloadFileWithRetry: (fileId: string, shouldRetry = true) => // Assuming GET /files/:id/download
        callWithRetry(api.get, [`/files/${fileId}/download`], shouldRetry),
      deleteFileWithRetry: (fileId: string, shouldRetry = true) =>
        callWithRetry(api.delete, [`/files/${fileId}`], shouldRetry),
      // Add more as needed
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