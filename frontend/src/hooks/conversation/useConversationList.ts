import { useState, useCallback, useEffect } from 'react';
import { v4 as uuidv4 } from 'uuid';
import useConversationStore from '../../store/conversationStore';
import { useEnhancedApi } from '../api';
import { 
  ConversationLoadState, 
  ConversationState, 
  ConversationListItem,
  Conversation
} from './types';

/**
 * Hook for managing the list of conversations.
 * Handles loading, creating, and deleting conversations.
 */
export const useConversationList = () => {
  console.log('[useConversationList] hook mounted');
  // State for conversation list operations
  const [state, setState] = useState<ConversationState>({
    loadState: ConversationLoadState.IDLE,
    error: null
  });

  // Get the enhanced API
  const { api, isOnline } = useEnhancedApi();

  // Get conversation state from store
  const {
    conversations,
    setConversations,
    addConversation,
    deleteConversation: removeConversationFromStore,
    setCurrentConversationId,
    currentConversationId
  } = useConversationStore();
  
  // Track loading state separately from the main state for smoother transitions
  const [isInitialized, setIsInitialized] = useState(false);
  
  /**
   * Load all conversations from the API
   * @returns Array of conversations
   */
  const loadConversations = useCallback(async () => {
    // Return early if already loading
    if (state.loadState === ConversationLoadState.LOADING) {
      console.log('Already loading conversations, skipping duplicate load');
      return conversations;
    }
    
    // Check if we already have conversations in the store
    if (conversations.length > 0) {
      console.log(`Found ${conversations.length} conversations already in store, using those instead of loading`);
      setIsInitialized(true);
      return conversations;
    }
    
    setState({
      loadState: ConversationLoadState.LOADING,
      error: null
    });
    
    try {
      // Try to load conversations with retry
      const response = await api.getConversationsWithRetry();
      console.log('Loaded conversations from API:', response);
      
      // Transform API response to match our store format
      const conversationsData = response.map((conv: any) => {
        // Convert UTC timestamps to local time
        const createdAt = new Date(conv.created_at);
        const updatedAt = new Date(conv.updated_at);
        
        return {
          id: conv.id,
          title: conv.title || 'New Conversation',
          messages: [], // We don't load messages here
          createdAt,
          updatedAt,
          isActive: conv.is_active,
        };
      });
      
      setConversations(conversationsData);
      setIsInitialized(true);
      
      setState({
        loadState: ConversationLoadState.LOADED,
        error: null
      });
      
      return conversationsData;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to load conversations';
      console.error('Error loading conversations:', errorMessage);
      
      setState({
        loadState: ConversationLoadState.ERROR,
        error: errorMessage
      });
      
      return [];
    }
  }, [api, conversations, setConversations, state.loadState]);
  
  /**
   * Create a new conversation
   * @param title Optional title for the new conversation
   * @returns ID of the new conversation
   */
  const createConversation = useCallback(async (title: string = 'New Conversation') => {
    setState({
      loadState: ConversationLoadState.LOADING,
      error: null
    });
    
    try {
      console.log('Creating new conversation:', title);
      
      // Generate a client-side ID for reference
      const clientSideId = uuidv4();
      
      // Create conversation on the server
      const response = await api.createConversationWithRetry({
        title
      });
      
      if (!response || !response.id) {
        throw new Error('Failed to create conversation: empty response');
      }
      
      // Use the ID returned from the server
      const conversationId = response.id;
      console.log('Created conversation with server ID:', conversationId);
      
      const newConversation: Conversation = {
        id: conversationId,
        title,
        messages: [
          // Add a welcome message from the assistant to ensure the conversation isn't empty
          {
            id: uuidv4(),
            role: 'assistant',
            content: 'Hi there! How can I help you today?',
            timestamp: new Date(),
            metadata: {}
          }
        ],
        createdAt: new Date(response.created_at) || new Date(),
        updatedAt: new Date(response.updated_at) || new Date(),
        isActive: true
      };
      
      // Add the new conversation to the store
      addConversation(newConversation);
      
      // Also add the welcome message to the server
      try {
        await api.addMessageWithRetry(conversationId, {
          content: 'Hi there! How can I help you today?',
          role: 'assistant'
        });
      } catch (err) {
        console.error('Failed to add welcome message:', err);
        // Continue anyway since the conversation was created
      }
      
      setState({
        loadState: ConversationLoadState.LOADED,
        error: null
      });
      
      return conversationId;
      
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to create conversation';
      console.error('Error creating conversation:', errorMessage);
      
      setState({
        loadState: ConversationLoadState.ERROR,
        error: errorMessage
      });
      
      return null;
    }
  }, [api, addConversation]);
  
  /**
   * Delete a conversation
   * @param conversationId ID of the conversation to delete
   * @returns Whether deletion was successful
   */
  const deleteConversation = useCallback(async (conversationId: string) => {
    console.log(`Deleting conversation with ID: ${conversationId}`);
    
    // Make sure we don't attempt to delete the only conversation
    if (conversations.length <= 1) {
      console.warn(`Cannot delete the only conversation. Creating a new one first.`);
      await createConversation('New Conversation');
    }
    
    try {
      // Delete from backend first
      console.log(`Calling API to delete conversation: ${conversationId}`);
      const response = await api.deleteConversationWithRetry(conversationId);
      console.log(`API delete response:`, response);
      
      // Then remove from local store
      console.log(`Removing conversation from store: ${conversationId}`);
      removeConversationFromStore(conversationId);
      
      return true;
    } catch (error) {
      console.error(`Failed to delete conversation ${conversationId}:`, error);
      
      // Remove from local store even if API call failed
      // This ensures UI consistency even if backend delete fails
      console.log(`API call failed, but still removing from store: ${conversationId}`);
      removeConversationFromStore(conversationId);
      
      return false;
    }
  }, [api, createConversation, conversations.length, removeConversationFromStore]);
  
  /**
   * Delete all conversations
   * @returns Whether the operation was successful
   */
  const deleteAllConversations = useCallback(async () => {
    console.log('Deleting all conversations...');
    
    try {
      // Create a new conversation first to prevent having 0 conversations
      console.log('Creating a new conversation before deleting all...');
      const newId = await createConversation('New Conversation');
      
      // Get all conversation IDs except the new one
      const idsToDelete = conversations
        .filter(conv => conv.id !== newId)
        .map(conv => conv.id);
      
      console.log(`Found ${idsToDelete.length} conversations to delete`);
      
      // Delete each conversation from the backend
      const deletePromises = idsToDelete.map(async (id) => {
        try {
          console.log(`Calling API to delete conversation: ${id}`);
          await api.deleteConversationWithRetry(id);
          console.log(`Successfully deleted conversation ${id} from API`);
          return { id, success: true };
        } catch (error) {
          console.error(`Failed to delete conversation ${id} from API:`, error);
          return { id, success: false };
        }
      });
      
      // Wait for all delete operations to complete
      const results = await Promise.all(deletePromises);
      
      // Remove all deleted conversations from store (whether API call succeeded or not)
      for (const id of idsToDelete) {
        console.log(`Removing conversation ${id} from store`);
        removeConversationFromStore(id);
      }
      
      const successCount = results.filter(r => r.success).length;
      console.log(`Deleted ${successCount}/${idsToDelete.length} conversations`);
      
      return true;
    } catch (error) {
      console.error('Failed to delete all conversations:', error);
      return false;
    }
  }, [api, conversations, createConversation, removeConversationFromStore]);
  
  // Initialize conversations on mount, but only if not already initialized
  useEffect(() => {
    console.log('[useConversationList] useEffect triggered. isInitialized:', isInitialized, 'isOnline:', isOnline);
    if (!isInitialized && isOnline) {
      console.log('[useConversationList] Calling loadConversations');
      loadConversations();
    }
  }, [isInitialized, isOnline, loadConversations]);
  
  // Prepare list items for UI
  const conversationList: ConversationListItem[] = conversations.map(conv => ({
    id: conv.id,
    title: conv.title,
    createdAt: conv.createdAt,
    updatedAt: conv.updatedAt,
    isActive: conv.isActive,
    preview: conv.messages[0]?.content?.toString().substring(0, 50) || '',
  }));
  
  return {
    conversationList,
    isLoading: state.loadState === ConversationLoadState.LOADING,
    isError: state.loadState === ConversationLoadState.ERROR,
    error: state.error,
    isInitialized,
    currentConversationId,
    
    // Actions
    loadConversations,
    createConversation,
    deleteConversation,
    deleteAllConversations,
    setCurrentConversationId,
  };
};

export default useConversationList; 