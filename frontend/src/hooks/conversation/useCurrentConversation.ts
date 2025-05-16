import { useState, useCallback, useEffect, useRef } from 'react';
import useConversationStore, { Conversation, Message } from '../../store/conversationStore';
import useFileStore, { FileItem } from '../../store/fileStore';
import { useEnhancedApi } from '../api';
import {
  ConversationLoadState,
  ConversationState,
  FileAttachment,
  PaginationState,
} from './types';

const MESSAGES_PER_PAGE = 50; // Define page size

/**
 * Hook for managing the current conversation.
 * Handles loading, displaying, and updating the active conversation.
 */
export const useCurrentConversation = () => {
  // State for current conversation operations
  const [state, setState] = useState<ConversationState>({
    loadState: ConversationLoadState.IDLE,
    error: null
  });

  // Get the enhanced API
  const { api } = useEnhancedApi();

  // Get conversation state from store
  const {
    conversations,
    currentConversationId,
    getCurrentConversation,
    updateConversation,
    addMessage,
    updateMessage,
    prependMessages,
    setConversationPagination
  } = useConversationStore();

  // Track loaded conversations to prevent redundant loading
  const loadedConversations = useRef<Set<string>>(new Set());

  // Define pagination state (using imported type)
  const [paginationState, setPaginationState] = useState<PaginationState>({
    isLoadingMore: false,
    hasMoreMessages: true, // Assume true initially
    oldestMessageId: null,
  });

  /**
   * Load the initial batch of messages for a specific conversation
   * @param id Conversation ID to load
   * @returns The loaded conversation or null if failed
   */
  const loadConversation = useCallback(async (id: string) => {
    if (!id) {
      console.error('No conversation ID provided to loadConversation');
      return null;
    }

    // At this point we need to load from API
    console.log(`Loading initial messages for conversation ${id} from API`);
    setState({ loadState: ConversationLoadState.LOADING, error: null });
    // Reset pagination state as we load all
    const initialPagination: PaginationState = { isLoadingMore: false, hasMoreMessages: true, oldestMessageId: null };
    setPaginationState(initialPagination);

    try {
      // Call API WITH pagination params - bypass retry for diagnostics
      console.log(`[Diagnostic] Calling api.getConversation directly for initial load: ID=${id}, Params=${JSON.stringify({ limit: MESSAGES_PER_PAGE })}`);
      const response = await api.getConversation(id, { limit: MESSAGES_PER_PAGE });

      if (!response) {
        throw new Error(`Conversation ${id} not found or API response invalid`);
      }
      const conversationData = response;

      const fetchedMessages = conversationData.messages || [];
      console.log(`API returned conversation ${id} with ${fetchedMessages.length} messages`);

      // Process fetched messages - DEFER FILE LOADING
      const allFiles = useFileStore.getState().files; // Get current file list
      
      console.log(`[loadConversation - ${id}] File store state contains ${allFiles.length} files. IDs:`, allFiles.map(f => f.id));
      const messages: Message[] = fetchedMessages.map((msg: any) => {
        const fileIds = msg.metadata?.file_ids || [];
        // --- ADDED: Log file IDs being processed ---
        if (fileIds.length > 0) {
          console.log(`[loadConversation - ${id}] Processing message ${msg.id} with file IDs:`, fileIds);
        }
        // --- END ADDED ---

        // Map file IDs to full FileAttachment objects
        const fileAttachments: FileAttachment[] = fileIds
          .map((fileId: string): FileAttachment | null => {
            const fileDetail = allFiles.find(f => f.id === fileId);
            if (fileDetail) {
              // Found details in the store
              return {
                id: fileDetail.id,
                name: fileDetail.filename,
                size: fileDetail.fileSize,
                type: fileDetail.fileType,
                url: `/api/v1/files/${fileDetail.id}/download`, // Construct download URL
                isUploading: false, // Assume not uploading when loading from history
                hasError: false,
                isDeleted: fileDetail.isDeleted,
                createdAt: fileDetail.createdAt,
                status: fileDetail.isDeleted ? 'error' : 'completed', // Basic status mapping
                errorMessage: fileDetail.isDeleted ? 'File deleted' : undefined,
                isActive: !fileDetail.isDeleted, // Consider active if not deleted
              };
            } else {
              // File details not found in store - might be deleted or inconsistent
              console.warn(`File details not found in store for ID: ${fileId}`);
              return null;
            }
          })
          .filter((att: FileAttachment | null): att is FileAttachment => att !== null); // Filter out nulls (though currently none)

        const timestamp = new Date(msg.created_at || msg.timestamp || Date.now()); // Ensure timestamp parsing is robust
        return {
          id: msg.id,
          content: msg.content || "",
          role: msg.role,
          timestamp,
          files: fileAttachments.length > 0 ? fileAttachments : undefined,
          metadata: msg.metadata
        };
      });

      // Reverse messages to store oldest-first, newest-last
      messages.reverse();

      // --- Re-enable Pagination Logic --- 
      // Extract pagination info from response (assuming it's nested under 'pagination')
      const hasMore = conversationData.pagination?.has_more ?? false; 
      
      console.log(`[API Check] Received hasMore from API: ${hasMore}`, conversationData.pagination);
      console.log(`[Pagination Debug] Parsed 'hasMore' from initial load response: ${hasMore}`, conversationData.pagination);
      
      let oldestMessageId: string | null = null;
      if (messages.length > 0) {
        // Messages should already be sorted descending by backend, find the last one (oldest)
        oldestMessageId = messages[messages.length - 1].id; 
      }
      
      const newPaginationState: PaginationState = {
        isLoadingMore: false,
        hasMoreMessages: hasMore,
        oldestMessageId: oldestMessageId,
      };
      setPaginationState(newPaginationState);
      console.log(`[Pagination Debug] Set oldestMessageId in pagination state: ${oldestMessageId}`);
      // --- End Pagination Logic ---

      // Create conversation object
      const conversation: Conversation = {
        id: conversationData.id,
        title: conversationData.title || 'New Conversation',
        createdAt: new Date(conversationData.created_at),
        updatedAt: new Date(conversationData.updated_at),
        messages,
        isActive: true,
        pagination: newPaginationState // Store pagination state
      };

      console.log(`Successfully loaded conversation ${id} with ${messages.length} messages`);
      loadedConversations.current.add(id);
      updateConversation(id, conversation); // Update store
      setState({ loadState: ConversationLoadState.LOADED, error: null });
      return conversation;

    } catch (err) {
        // Log the full error object for more details
        console.error(`Error loading conversation ${id}:`, err);
        const errorMessage = err instanceof Error ? err.message : String(err); // Get message or stringify
        console.error(`Parsed error message for state:`, errorMessage);

        setState({ loadState: ConversationLoadState.ERROR, error: errorMessage });
        // Ensure pagination state reflects error? Maybe set hasMore to false?
        // Let's keep hasMoreMessages as it was, don't assume error means no more messages.
        setPaginationState(prev => ({ ...prev, isLoadingMore: false })); 
        return null;
    }
  }, [api, updateConversation, getCurrentConversation]);

  // Load the current conversation when ID changes or state requires it
  useEffect(() => {
    if (!currentConversationId) {
      console.log("[Pagination Debug] useEffect [v3]: No currentConversationId, skipping.");
      return;
    }

    console.log(`[Pagination Debug] useEffect [v3]: Checking conversation ${currentConversationId}. Load state: ${state.loadState}`);

    // Always skip if already loading or in a final error state
    if (state.loadState === ConversationLoadState.LOADING) {
      console.log(`[Pagination Debug] useEffect [v3]: State is LOADING, skipping load trigger.`);
      return;
    }
    else if (state.loadState === ConversationLoadState.ERROR) {
      console.log(`[Pagination Debug] useEffect [v3]: State is ERROR, skipping load trigger.`);
      return;
    }

    // --- ADDED: Delay before checking rehydration state ---
    const checkTimer = setTimeout(() => {
      console.log("[Rehydration Check] Running delayed check...");
      
      // --- Check for incomplete file data after rehydration ---
      const currentConv = getCurrentConversation();
      // --- ADDED: Log currentConv state ---
      console.log(`[Rehydration Check - CONV STATE] currentConv:`, 
        currentConv ? 
        { id: currentConv.id, messageCount: currentConv.messages?.length, firstMsgFiles: currentConv.messages?.[0]?.files } : 
        null
      );
      // --- END ADDED ---
      let needsFilePopulation = false;
      if (currentConv && currentConv.messages) {
        // --- ADDED: Log entering the inner check ---
        console.log(`[Rehydration Check - INNER CHECK] Entered check for conv ${currentConv.id}`);
        // --- END ADDED ---
        needsFilePopulation = currentConv.messages.some(msg => {
          const hasFileIds = msg.metadata?.file_ids && msg.metadata.file_ids.length > 0;
          // --- REVISED CHECK: Check if files property is missing or empty ---
          const filesMissingOrEmpty = !msg.files || msg.files.length === 0; 
          return hasFileIds && filesMissingOrEmpty;
          // --- END REVISED CHECK ---
        });
        
        if (needsFilePopulation) {
          console.log(`[Rehydration Check] Conversation ${currentConversationId} needs file details populated. Forcing load.`);
          // --- ADDED: Confirm trigger --- 
          console.log(`[Rehydration Check - TRIGGERING] Calling loadConversation(${currentConversationId}) NOW.`);
          // --- END ADDED ---
          // Force load if files are missing details
          loadConversation(currentConversationId);
          return; // Exit useEffect after triggering load
        }
      }
      // --- END ADDED ---

      // Check if this specific conversation has already been successfully loaded and tracked.
      // We only trigger loadConversation if it's IDLE, or if the conversation ID
      // changed to one that hasn't been successfully loaded *and added to the ref* yet.
      if (state.loadState === ConversationLoadState.LOADED && loadedConversations.current.has(currentConversationId)) {
        console.log(`[Pagination Debug] useEffect [v3]: State is LOADED and conversation ${currentConversationId} is already tracked in loadedConversations ref. Skipping load trigger.`);
        // If needed, ensure pagination state is synced from store (optional optimization)
        // const currentConv = getCurrentConversation();
        // if (currentConv?.pagination && ...) { setPaginationState(currentConv.pagination); }
        return;
      }

      // 5. If not returned yet, trigger load
      console.log(`[!!!] useEffect [v3]: PRE-LOAD CHECK for Conv ${currentConversationId}: state=${state.loadState}, tracked=${loadedConversations.current.has(currentConversationId)}`);
      console.log(`[Pagination Debug] useEffect [v3]: Triggering loadConversation(${currentConversationId}) because state is ${state.loadState} and/or conversation not tracked.`);
      loadConversation(currentConversationId);
      
    }, 200); // Delay of 200ms
    // --- END ADDED ---

  // DEPENDENCY CHANGE: Only react to the ID changing. State checks happen inside.
  }, [currentConversationId]); // REMOVE loadConversation dependency

  /**
   * Update conversation title
   * @param title New title for the conversation
   */
  const updateTitle = useCallback(async (title: string) => {
    if (!currentConversationId) return;
    
    try {
      // Update locally first for immediate UI feedback
      updateConversation(currentConversationId, { title });
      
      // Then update on the server
      await api.updateConversationWithRetry(currentConversationId, { title });
    } catch (err) {
      console.error('Failed to update conversation title:', err);
    }
  }, [api, currentConversationId, updateConversation]);

  /**
   * Clear the loaded conversations cache to force reload
   */
  const clearLoadedConversationsCache = useCallback(() => {
    loadedConversations.current.clear();
  }, []);

  /**
   * Load more messages (older ones) for the current conversation
   */
  const loadMoreMessages = useCallback(async () => {
    if (!currentConversationId || paginationState.isLoadingMore || !paginationState.hasMoreMessages) {
      console.log('Cannot load more messages:', {
        currentConversationId,
        isLoadingMore: paginationState.isLoadingMore,
        hasMoreMessages: paginationState.hasMoreMessages
      });
      return;
    }

    // Use oldestMessageId as the cursor
    const cursor = paginationState.oldestMessageId;
    if (!cursor) {
      console.warn('Cannot load more messages without a cursor (oldestMessageId).');
      setPaginationState(prev => ({ ...prev, isLoadingMore: false }));
      return;
    }

    console.log(`Loading more messages for ${currentConversationId} before message ${cursor}`);
    setPaginationState(prev => ({ ...prev, isLoadingMore: true }));

    try {
      // Call API WITH pagination params - bypass retry for diagnostics
      // OLD: const response = await api.getConversationWithRetry(id, { limit: MESSAGES_PER_PAGE }, true);
      console.log(`[Diagnostic] Calling api.getConversation directly for load more: ID=${currentConversationId}, Params=${JSON.stringify({ limit: MESSAGES_PER_PAGE, before_message_id: cursor })}`);
      const response = await api.getConversation(currentConversationId, { limit: MESSAGES_PER_PAGE, before_message_id: cursor });

      if (!response) {
        throw new Error(`Invalid response when loading more messages for ${currentConversationId}`);
      }
      const conversationData = response;
      const fetchedMessages = conversationData.messages || [];
      const hasMore = conversationData.pagination?.has_more ?? false;

      console.log(`API returned ${fetchedMessages.length} older messages. Has more: ${hasMore}`);

      if (fetchedMessages.length === 0) {
        setPaginationState(prev => ({ ...prev, hasMoreMessages: false, isLoadingMore: false }));
        if (setConversationPagination) {
          setConversationPagination(currentConversationId, { hasMoreMessages: false });
        }
        return;
      }

      // Process messages - DEFER FILE LOADING
      const allFiles = useFileStore.getState().files; // Get current file list
      
      console.log(`[loadMoreMessages - ${currentConversationId}] File store state contains ${allFiles.length} files.`);
      const olderMessages: Message[] = fetchedMessages.map((msg: any) => {
        const fileIds = msg.metadata?.file_ids || [];
        // --- ADDED: Log file IDs being processed in loadMore ---
        if (fileIds.length > 0) {
          console.log(`[loadMoreMessages - ${currentConversationId}] Processing message ${msg.id} with file IDs:`, fileIds);
        }
        // --- END ADDED ---

        // Map file IDs to full FileAttachment objects
        const fileAttachments: FileAttachment[] = fileIds
          .map((fileId: string): FileAttachment | null => {
            const fileDetail = allFiles.find(f => f.id === fileId);
            if (fileDetail) {
              // Found details in the store
              return {
                id: fileDetail.id,
                name: fileDetail.filename,
                size: fileDetail.fileSize,
                type: fileDetail.fileType,
                url: `/api/v1/files/${fileDetail.id}/download`, // Construct download URL
                isUploading: false, // Assume not uploading when loading from history
                hasError: false,
                isDeleted: fileDetail.isDeleted,
                createdAt: fileDetail.createdAt,
                status: fileDetail.isDeleted ? 'error' : 'completed', // Basic status mapping
                errorMessage: fileDetail.isDeleted ? 'File deleted' : undefined,
                isActive: !fileDetail.isDeleted, // Consider active if not deleted
              };
            } else {
              // File details not found in store - might be deleted or inconsistent
              console.warn(`File details not found in store for ID: ${fileId} during loadMore`);
              return null;
            }
          })
          .filter((att: FileAttachment | null): att is FileAttachment => att !== null); // Filter out nulls

        const timestamp = new Date(msg.created_at || msg.timestamp || Date.now()); // Ensure timestamp parsing is robust
        return {
          id: msg.id,
          content: msg.content || "",
          role: msg.role,
          timestamp,
          files: fileAttachments.length > 0 ? fileAttachments : undefined,
          metadata: msg.metadata
        };
      });

      // Reverse messages to store oldest-first, newest-last for prepending
      olderMessages.reverse();

      // Determine the new oldest message ID from the fetched batch
      const newOldestMessageId = olderMessages.length > 0 ? olderMessages[olderMessages.length - 1].id : cursor; 

      const newPaginationState: PaginationState = {
        isLoadingMore: false,
        hasMoreMessages: hasMore,
        oldestMessageId: newOldestMessageId
      };
      setPaginationState(newPaginationState);

      console.log(`[Pagination Debug] Processed ${olderMessages.length} older messages. New pagination state:`, newPaginationState);

      // Prepend messages to the store
      if (prependMessages) {
        console.log(`[Pagination Debug] Calling prependMessages for conversation ${currentConversationId}...`);
        prependMessages(currentConversationId, olderMessages, newPaginationState);
        console.log(`[Pagination Debug] prependMessages call completed.`);
      } else {
        console.warn('prependMessages function not available in store!');
        // Fallback logic (less efficient)
        const currentConv = getCurrentConversation();
        if (currentConv) {
          updateConversation(currentConversationId, {
             messages: [...olderMessages.reverse(), ...currentConv.messages], // Ensure correct order
             pagination: newPaginationState 
          });
        }
      }
      console.log(`Successfully prepended ${olderMessages.length} older messages.`);

    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : `Failed to load more messages for ${currentConversationId}`;
      console.error(`Error loading more messages for ${currentConversationId}:`, errorMessage);
      // On error, stop loading and prevent further attempts by setting hasMore to false
      setPaginationState(prev => ({
        ...prev,
        isLoadingMore: false,
        hasMoreMessages: false // Prevent immediate retries
      }));
      // Also update the store if possible
      if (setConversationPagination) {
        setConversationPagination(currentConversationId, { hasMoreMessages: false });
      }
    }
  }, [api, currentConversationId, paginationState, prependMessages, setConversationPagination, updateConversation, getCurrentConversation]);

  // Add sendMessage function (modified for API signature and response check)
  const sendMessage = useCallback(async (text: string, attachments: FileAttachment[] = []) => {
    if (!currentConversationId) {
      throw new Error('No active conversation');
    }

    if (!text.trim() && attachments.length === 0) {
      throw new Error('Message cannot be empty unless attaching files');
    }
    
    const tempMessageId = `temp-${Date.now()}`;

    try {
      const tempMessage: Message = {
        id: tempMessageId,
        content: text,
        role: 'user',
        timestamp: new Date(),
        files: attachments
      };
      addMessage(currentConversationId, tempMessage);

      // Call API using the signature found: (text, conversationId, attachments)
      const response: any = await api.sendMessageWithRetry(text, currentConversationId, attachments);

      // Check response structure - ADJUST IF NEEDED based on actual API response
      if (!response || !response.id) { 
        console.error('Invalid response from sendMessageWithRetry:', response);
        throw new Error('Invalid response from server when sending message');
      }

      const serverMessageData = response; 
      updateMessage(currentConversationId, tempMessageId, { 
        ...tempMessage,
        id: serverMessageData.id, 
        timestamp: new Date(serverMessageData.created_at || serverMessageData.timestamp || Date.now())
      });

      return serverMessageData; 
    } catch (error) {
      console.error('Error sending message:', error);
      if (currentConversationId) {
        // Update message to show error state rather than deleting
        updateMessage(currentConversationId, tempMessageId, { content: `[Error sending message: ${error instanceof Error ? error.message : 'Unknown error'}]`, role: 'system' }); 
      }
      throw error;
    }
  }, [currentConversationId, addMessage, updateMessage, api]);

  // Get the current conversation
  const currentConversation = getCurrentConversation();

  // Define returnValue AFTER all functions (like loadMoreMessages) are defined
  const returnValue = {
    currentConversation, // The actual conversation object or null
    loadState: state.loadState, // The raw load state enum
    isLoading: state.loadState === ConversationLoadState.LOADING, // Derived boolean for initial loading
    isLoadingMore: paginationState.isLoadingMore, // Kept for UI consistency, but won't be true
    hasMoreMessages: paginationState.hasMoreMessages, // Kept for UI consistency, but will be false
    isError: state.loadState === ConversationLoadState.ERROR, // Derived boolean for error state
    error: state.error, // Actual error message
    
    // Actions
    loadConversation, // Function for initial load (fetches all)
    loadMoreMessages, // Non-functional placeholder
    updateTitle, // Function to update title
    clearLoadedConversationsCache, // Function to clear cache
    sendMessage, // Function to send a message
    
    // Pass-through store actions
    addMessage, 
    updateMessage, 
    prependMessages, // Kept for store API consistency
    setConversationPagination // Kept for store API consistency
  };

  return returnValue;
};

export default useCurrentConversation; 