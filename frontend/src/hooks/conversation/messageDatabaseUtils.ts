import { useCallback } from 'react';
import useConversationStore from '../../store/conversationStore';
import { useEnhancedApi } from '../api';

/**
 * Utility hook with functions for saving messages to the database
 * with automatic conversation creation if needed
 */
export const useMessageDatabaseUtils = () => {
  // Get the enhanced API
  const { api } = useEnhancedApi();
  
  // Get conversation store actions
  const { getCurrentConversation } = useConversationStore();

  /**
   * Helper function to save a message to the database with error handling
   * If the conversation doesn't exist in the database, creates it first
   */
  const saveMessageToDatabase = useCallback(async (
    conversationId: string,
    content: string,
    role: 'user' | 'assistant' | 'system',
    metadata: any = {}
  ) => {
    console.log('🔴 SAVE MESSAGE TO DB CALLED:', {
      conversationId,
      role,
      contentPreview: typeof content === 'string' ? 
        (content.substring(0, 50) + '...') : 
        String(content || '').substring(0, 50) + '...',
    });
    
    try {
      // Try to save the message
      console.log('🔴 Attempting to save message via API...');
      await api.addMessageWithRetry(conversationId, {
        content,
        role,
        metadata
      });
      console.log(`🔴 SAVED ${role.toUpperCase()} MESSAGE TO DATABASE`);
      return true;
    } catch (error: any) {
      // If the conversation doesn't exist (404), create it first then retry
      if (error && error.message && error.message.includes('404')) {
        console.log(`🔴 Conversation ${conversationId} not found in database, creating it first`);
        try {
          // Get the current conversation from the store to use as a base
          const currentConv = getCurrentConversation();
          const title = currentConv?.title || 'New Conversation';
          
          // Create the conversation in the database
          console.log('🔴 Creating new conversation in database...');
          const response = await api.createConversationWithRetry({
            title
          });
          
          if (!response || !response.id) {
            console.error('🔴 Failed to create conversation: empty response');
            throw new Error('Failed to create conversation: empty response');
          }
          
          const serverConversationId = response.id;
          console.log(`🔴 Created new conversation with server ID: ${serverConversationId}, need to update our local ID from ${conversationId}`);
          
          // Now try to save the message to the new conversation ID
          console.log('🔴 Saving message to new conversation ID...');
          await api.addMessageWithRetry(serverConversationId, {
            content,
            role,
            metadata
          });
          console.log(`🔴 Created conversation and saved ${role} message to database with new ID: ${serverConversationId}`);
          
          // TODO: We should update our local store to use the new ID
          // This is a more complex fix that would require changes to the store structure
          // For now, we'll just log a warning
          console.warn(`🔴 Local conversation ID (${conversationId}) and server ID (${serverConversationId}) mismatch. This will cause issues with message persistence.`);
          
          return true;
        } catch (createError) {
          console.error('🔴 Failed to create conversation and save message:', createError);
          return false;
        }
      }
      
      console.error(`🔴 Failed to save ${role} message to database:`, error);
      return false;
    }
  }, [api, getCurrentConversation]);

  return {
    saveMessageToDatabase
  };
};

export default useMessageDatabaseUtils; 