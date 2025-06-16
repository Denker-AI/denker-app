import { useState, useCallback, useRef, useEffect } from 'react';
import { v4 as uuidv4 } from 'uuid';
import useConversationStore from '../../store/conversationStore';
import { useEnhancedApi } from '../api';
import useMessageDatabaseUtils from './messageDatabaseUtils';
import {
  ConversationLoadState,
  ConversationState,
  FileAttachment,
  SendMessageResult
} from './types';
import { useApiStatus, ApiStatus } from '../api/useApiStatus';
import useRealTimeUpdates from './useRealTimeUpdates';

/**
 * Hook for sending messages and handling file attachments
 */
export const useMessageSender = () => {
  // State for sending operations
  const [state, setState] = useState<ConversationState>({
    loadState: ConversationLoadState.IDLE,
    error: null
  });
  
  // Delayed loading state - only show loading UI after 5 seconds
  const [showLoading, setShowLoading] = useState(false);
  const loadingTimerRef = useRef<NodeJS.Timeout | null>(null);

  // Get the enhanced API
  const { api } = useEnhancedApi();
  const { apiStatus } = useApiStatus();
  const { activeQueryId } = useRealTimeUpdates();

  // Get conversation store actions
  const {
    currentConversationId,
    addMessage,
    updateMessage,
    updateConversation,
    getCurrentConversation
  } = useConversationStore();
  
  // Get database utilities
  const { saveMessageToDatabase } = useMessageDatabaseUtils();
  
  // Clear timer on unmount
  useEffect(() => {
    return () => {
      if (loadingTimerRef.current) {
        clearTimeout(loadingTimerRef.current);
      }
    };
  }, []);
  
  // Monitor loading state and set delayed loading UI
  useEffect(() => {
    if (state.loadState === ConversationLoadState.LOADING) {
      // Clear any existing timer
      if (loadingTimerRef.current) {
        clearTimeout(loadingTimerRef.current);
      }
      
      // Set a new timer for 5 seconds
      loadingTimerRef.current = setTimeout(() => {
        setShowLoading(true);
      }, 5000);
    } else {
      // Not loading anymore, clear timer and hide loading UI
      if (loadingTimerRef.current) {
        clearTimeout(loadingTimerRef.current);
        loadingTimerRef.current = null;
      }
      setShowLoading(false);
    }
    
    // Add global reset function for other components to use
    // @ts-ignore - Add to window object
    window.resetMessageLoadingState = () => {
      console.log('Manual reset of message loading state');
      setState({
        loadState: ConversationLoadState.IDLE,
        error: null
      });
      
      if (loadingTimerRef.current) {
        clearTimeout(loadingTimerRef.current);
        loadingTimerRef.current = null;
      }
      setShowLoading(false);
    };
    
    // Clean up function when unmounting
    return () => {
      // @ts-ignore - Remove from window object
      window.resetMessageLoadingState = undefined;
    };
  }, [state.loadState]);

  /**
   * Send a message with optional file attachments
   * @param content Message text content
   * @param files Optional array of files to attach
   * @returns Result with success status and IDs
   */
  const sendMessage = useCallback(async (
    content: string, 
    files?: File[]
  ): Promise<SendMessageResult> => {
    // Validation - we need content or files, and a current conversation
    if ((!content.trim() && (!files || files.length === 0))) {
      return { 
        success: false, 
        conversationId: null, 
        messageId: null,
        error: 'No content or files to send'
      };
    }

    const convId = currentConversationId;
    if (!convId) {
      setState({
        loadState: ConversationLoadState.ERROR,
        error: 'No conversation selected'
      });
      return { 
        success: false, 
        conversationId: null, 
        messageId: null,
        error: 'No conversation selected'
      };
    }

    try {
      // Start the loading state
      setState({
        loadState: ConversationLoadState.LOADING,
        error: null
      });

      // Create a new message ID
      const userMessageId = uuidv4();
      const currentTime = new Date();
      
      // Handle files if provided
      let fileAttachments: FileAttachment[] = [];
      let finalFileIds: string[] = [];

      if (files && files.length > 0) {
        // Create temporary file attachments for display while uploading
        fileAttachments = files.map(file => ({
          id: `temp-${uuidv4()}`,
          name: file.name,
          size: file.size,
          type: file.type,
          url: '',
          isUploading: true
        }));

        // Add user message with pending file attachments
        addMessage(convId, {
          id: userMessageId,
          content,
          role: 'user',
          timestamp: currentTime,
          files: fileAttachments
        });

        // Get the current conversation before potentially updating title
        const currentConv = getCurrentConversation();

        // If this is the first user message, use it as conversation title
        if (currentConv && 
            (currentConv.messages.length <= 1 || 
             !currentConv.messages.some(msg => msg.role === 'user' && msg.id !== userMessageId))) {
          // Add safety check to ensure content is a string
          const contentStr = typeof content === 'string' ? content : String(content || '');
          const newTitle = contentStr.length > 30 
            ? `${contentStr.substring(0, 30)}...` 
            : contentStr;
          
          // Update title locally and on server
          updateConversation(convId, { title: newTitle });
          api.updateConversation(convId, { title: newTitle })
            .catch(err => console.error('Failed to update conversation title:', err));
        }

        // Upload files and collect their IDs
        const uploadPromises = files.map(async (file, index) => {
          try {
            // --- MODIFIED: Use uploadFileWithRetry and pass IDs --- 
            const currentQueryId = activeQueryId; // Get the current active query ID
            console.log(`Uploading file ${file.name} for message ${userMessageId} with queryId ${currentQueryId}`);
            const uploadResponse = await api.uploadFileWithRetry(file, { query_id: currentQueryId ?? undefined, message_id: userMessageId });
            // --- END MODIFICATION ---
            const fileData = uploadResponse;

            // Update the temporary file with real data
            const updatedFileAttachment = {
              id: fileData.id,
              name: file.name,
              size: file.size,
              type: file.type,
              url: fileData.url || `/api/v1/files/${fileData.id}/download`,
              isUploading: false
            };

            // Update the message with real file data
            const currentMessage = getCurrentConversation()?.messages.find(m => m.id === userMessageId);
            if (currentMessage && currentMessage.files) {
              const updatedFiles = [...currentMessage.files];
              updatedFiles[index] = updatedFileAttachment;

              // Update the message
              updateMessage(convId, userMessageId, {
                files: updatedFiles
              });
            }

            return fileData.id;
          } catch (error) {
            console.error(`Failed to upload file ${file.name}:`, error);
            // Update file to show error state
            const currentMessage = getCurrentConversation()?.messages.find(m => m.id === userMessageId);
            if (currentMessage && currentMessage.files) {
              const updatedFiles = [...currentMessage.files];
              updatedFiles[index] = {
                ...updatedFiles[index],
                isUploading: false,
                hasError: true
              };

              // Update the message with error state
              updateMessage(convId, userMessageId, {
                files: updatedFiles
              });
            }
            return null;
          }
        });

        // Wait for all uploads and filter out failed ones
        finalFileIds = (await Promise.all(uploadPromises)).filter(Boolean) as string[];
        
        // Save the message to the database with file IDs
        const metadataForSave = finalFileIds.length > 0 ? { file_ids: finalFileIds } : {};
        console.log('🔴 [useMessageSender] Calling saveMessageToDatabase (with files):', {
          convId,
          userMessageId,
          content, // User's text input
          role: 'user',
          metadata: metadataForSave
        });
        await saveMessageToDatabase(
          convId, 
          userMessageId,
          content, 
          'user', 
          metadataForSave
        ).catch(err => console.error('Database persistence failed, but UI is updated:', err));
      } else {
        // If no files, just add the text message
        addMessage(convId, {
          id: userMessageId,
          content,
          role: 'user',
          timestamp: currentTime
        });

        // Save the message to the database
        console.log('🔴 [useMessageSender] Calling saveMessageToDatabase (no files):', {
          convId,
          userMessageId,
          content, // User's text input
          role: 'user',
          metadata: {} // Explicitly empty for this path
        });
        await saveMessageToDatabase(convId, userMessageId, content, 'user') // metadata defaults to {}
          .catch(err => console.error('Database persistence failed, but UI is updated:', err));

        // Check if this is the first message and update title if needed
        const currentConv = getCurrentConversation();
        if (currentConv && 
            (currentConv.messages.length <= 1 || 
             !currentConv.messages.some(msg => msg.role === 'user' && msg.id !== userMessageId))) {
          // Add safety check to ensure content is a string
          const contentStr = typeof content === 'string' ? content : String(content || '');
          const newTitle = contentStr.length > 30 
            ? `${contentStr.substring(0, 30)}...` 
            : contentStr;
          
          updateConversation(convId, { title: newTitle });
          api.updateConversation(convId, { title: newTitle })
            .catch(err => console.error('Failed to update conversation title:', err));
        }
      }

      // Update the conversation's last update time
      updateConversation(convId, { updatedAt: new Date() });
      
      // Reset the loading state - we'll do this after the coordinator call, 
      // not after adding the message to the UI
      // We want loading indicator for coordinator response only
      
      return {
        success: true,
        conversationId: convId,
        messageId: userMessageId
      };
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to send message';
      console.error('Failed to send message:', errorMessage);
      
      setState({
        loadState: ConversationLoadState.ERROR,
        error: errorMessage
      });
      
      return {
        success: false,
        conversationId: convId,
        messageId: null,
        error: errorMessage
      };
    }
  }, [api, currentConversationId, addMessage, updateMessage, updateConversation, getCurrentConversation, saveMessageToDatabase, activeQueryId]);

  return {
    sendMessage,
    isLoading: state.loadState === ConversationLoadState.LOADING,
    showLoading, // Use this for UI indicators
    isError: state.loadState === ConversationLoadState.ERROR,
    error: state.error
  };
};

export default useMessageSender; 