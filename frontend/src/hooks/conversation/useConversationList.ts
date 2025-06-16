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
      return useConversationStore.getState().conversations;
    }
    
    const currentConversations = useConversationStore.getState().conversations;
    
    // If we have persisted conversations, use them immediately but validate with API
    if (currentConversations.length > 0) {
      console.log('[useConversationList] Using persisted conversations:', currentConversations.length);
      
      // Mark as initialized immediately to prevent UI flashing
      setIsInitialized(true);
      
      // Auto-select first conversation if no current conversation is set
      if (!currentConversationId) {
        console.log('[useConversationList] Auto-selecting first conversation:', currentConversations[0].id);
        setCurrentConversationId(currentConversations[0].id);
      }
      
      // Background validation with API (don't update store if it causes issues)
      api.getConversationsWithRetry().then(response => {
        console.log('Background sync: Loaded conversations from API:', response.length);
        
                          // Only update if the data is significantly different to avoid unnecessary re-renders
         const typedResponse = response as Array<{id: string, [key: string]: any}>;
         const apiConversationIds = new Set(typedResponse.map(conv => conv.id));
         const currentConversationIds = new Set(currentConversations.map(conv => conv.id));
         
         const hasSignificantChanges = 
           apiConversationIds.size !== currentConversationIds.size ||
           [...apiConversationIds].some(id => !currentConversationIds.has(id));
        
        if (hasSignificantChanges) {
          console.log('Background sync: Significant changes detected, updating store');
          const conversationsData = response.map((conv: any) => ({
            id: conv.id,
            title: conv.title || 'New Conversation',
            messages: [], // We don't load messages here
            createdAt: new Date(conv.created_at),
            updatedAt: new Date(conv.updated_at),
            isActive: conv.is_active,
          }));
          
          setConversations(conversationsData);
        } else {
          console.log('Background sync: No significant changes, keeping persisted data');
        }
        
      }).catch(err => {
        console.warn('Background sync failed, continuing with persisted data:', err);
        // Don't set error state since we have persisted data
      });
      
      return currentConversations;
    }
    
    // No persisted conversations - this is initial load, show loading
    console.log('[useConversationList] No persisted conversations, initial load from API');
    setState({
      loadState: ConversationLoadState.LOADING,
      error: null
    });
    
    try {
      // Try to load conversations with retry
      const response = await api.getConversationsWithRetry();
      console.log('Initial load: Loaded conversations from API:', response.length);
      
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
      
      // Handle empty conversations case - only create if we don't already have one being created
      if (conversationsData.length === 0) {
        // Check if there's already a conversation in the store (e.g., created by MainWindow)
        const currentConversations = useConversationStore.getState().conversations;
        if (currentConversations.length > 0) {
          console.log('[useConversationList] No API conversations but found existing local conversations, skipping default creation');
        } else {
          console.log('[useConversationList] No conversations found, creating default conversation');
          try {
            // Create conversation on the server first
            const createResponse = await api.createConversationWithRetry({
              title: 'New Conversation'
            });
            
            if (createResponse && createResponse.id) {
              const conversationId = createResponse.id;
              console.log('[useConversationList] Created default conversation with server ID:', conversationId);
              
              const defaultConversation: Conversation = {
                id: conversationId,
                title: 'New Conversation',
                messages: [
                  // Add a welcome message to ensure the conversation isn't empty
                  {
                    id: uuidv4(),
                    role: 'assistant',
                    content: 'Hi there! How can I help you today?',
                    timestamp: new Date(),
                    metadata: {}
                  }
                ],
                createdAt: new Date(createResponse.created_at) || new Date(),
                updatedAt: new Date(createResponse.updated_at) || new Date(),
                isActive: true
              };
              
              // Add to store and set as current
              addConversation(defaultConversation);
              setCurrentConversationId(conversationId);
              
              // Also add the welcome message to the server
              try {
                await api.addMessageWithRetry(conversationId, {
                  content: 'Hi there! How can I help you today?',
                  role: 'assistant'
                });
              } catch (err) {
                console.error('[useConversationList] Failed to add welcome message to default conversation:', err);
                // Continue anyway since the conversation was created
              }
            }
          } catch (err) {
            console.error('[useConversationList] Failed to create default conversation:', err);
            // If server creation fails, create a local-only conversation to prevent empty state
            const localConversation: Conversation = {
              id: `local-${uuidv4()}`,
              title: 'New Conversation',
              messages: [
                {
                  id: uuidv4(),
                  role: 'assistant',
                  content: 'Hi there! How can I help you today?',
                  timestamp: new Date(),
                  metadata: {}
                }
              ],
              createdAt: new Date(),
              updatedAt: new Date(),
              isActive: true
            };
            
            console.log('[useConversationList] Created fallback local conversation');
            addConversation(localConversation);
            setCurrentConversationId(localConversation.id);
          }
        }
      } else {
        // Auto-select first conversation if no current conversation is set
        if (!currentConversationId) {
          console.log('[useConversationList] Auto-selecting first conversation from API:', conversationsData[0].id);
          setCurrentConversationId(conversationsData[0].id);
        }
      }
      
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
  }, [api, setConversations, addConversation, setCurrentConversationId, currentConversationId, state.loadState]);
  
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
    if (useConversationStore.getState().conversations.length <= 1) {
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
  }, [api, createConversation, removeConversationFromStore]);
  
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
      const idsToDelete = useConversationStore.getState().conversations
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
  }, [api, createConversation, removeConversationFromStore]);
  
  // Initialize conversations on mount, but only if not already initialized
  useEffect(() => {
    console.log('[useConversationList] useEffect triggered. isInitialized:', isInitialized);
    if (!isInitialized) {
      console.log('[useConversationList] Calling loadConversations for initial load.');
      loadConversations();
    }
  }, [isInitialized, loadConversations]);
  
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