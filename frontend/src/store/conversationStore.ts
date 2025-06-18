import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import { v4 as uuidv4 } from 'uuid';
import { immer } from 'zustand/middleware/immer';
import { PaginationState, FileAttachment } from '../hooks/conversation/types'; // Import shared types

export interface Message {
  id: string;
  content: string | any;  // Allow structured content
  role: 'user' | 'assistant' | 'system';
  timestamp: Date;
  files?: FileAttachment[];
  metadata?: Record<string, any>;
  type?: 'thinking' | 'tool_call' | 'result' | 'synthesis';  // New field for coordinator steps
  tool?: {
    name: string;
    query: string;
  };
  source?: 'document' | 'web';  // For result messages
}

export interface Conversation {
  id: string;
  title: string;
  messages: Message[];
  createdAt: Date;
  updatedAt: Date;
  isActive: boolean;
  pagination?: PaginationState;
}

interface ConversationState {
  conversations: Conversation[];
  currentConversationId: string | null;
  isLoading: boolean;
  error: string | null;
  
  // Actions
  setConversations: (conversations: Conversation[]) => void;
  addConversation: (conversation: Partial<Conversation>) => string;
  updateConversation: (id: string, updates: Partial<Conversation>) => void;
  deleteConversation: (id: string) => void;
  setCurrentConversationId: (id: string | null) => void;
  clearAllConversations: () => void;
  
  // Message actions
  addMessage: (conversationId: string, message: Message) => void;
  updateMessage: (conversationId: string, messageId: string, updates: Partial<Message>) => void;
  deleteMessage: (conversationId: string, messageId: string) => void;
  updateFileAttachmentStatus: (
    conversationId: string, 
    messageId: string,
    fileId: string,
    status: FileAttachment['status'],
    errorMessage?: string
  ) => void;
  
  // Pagination actions
  prependMessages: (conversationId: string, messages: Message[], pagination: PaginationState) => void;
  setConversationPagination: (conversationId: string, pagination: Partial<PaginationState>) => void;
  
  // Loading state
  setLoading: (isLoading: boolean) => void;
  setError: (error: string | null) => void;
  
  // Helpers
  getCurrentConversation: () => Conversation | null;
  // createNewConversation: () => string; // COMMENTED OUT: Unused method
  
  // Debug/Reset methods
  resetStore: () => void;
  repairConversation: (id: string) => boolean;
  
  // User management methods
  switchUser: (userId: string | null) => void;
  getCurrentUserId: () => string | null;
}

// Store the current user ID to detect user changes
let currentUserId: string | null = null;

const useConversationStore = create<ConversationState>()(
  persist(
    (set, get) => ({
      conversations: [],
      currentConversationId: null,
      isLoading: false,
      error: null,
      
      // Actions
      setConversations: (conversations) => set({ conversations }),
      
      addConversation: (conversation) => {
        const newConversation: Conversation = {
          id: conversation.id || uuidv4(),
          title: conversation.title || 'New Conversation',
          messages: conversation.messages || [],
          createdAt: conversation.createdAt || new Date(),
          updatedAt: conversation.updatedAt || new Date(),
          isActive: conversation.isActive !== undefined ? conversation.isActive : true,
          pagination: conversation.pagination || {
            isLoadingMore: false,
            hasMoreMessages: true,
            oldestMessageId: null
          },
        };
        
        set((state) => ({
          conversations: [...state.conversations, newConversation],
          currentConversationId: newConversation.id,
        }));
        
        return newConversation.id;
      },
      
      updateConversation: (id, updates) => {
        console.log(`STORE DEBUG: Updating conversation ${id}`);
        console.log('STORE DEBUG: Update payload:', updates);
        
        set((state) => {
          // Find the conversation being updated
          const existingConv = state.conversations.find(conv => conv.id === id);
          
          if (!existingConv) {
            console.log(`STORE DEBUG: Conversation ${id} not found in state, adding new`);
          } else {
            console.log(`STORE DEBUG: Existing conversation has ${existingConv.messages.length} messages`);
            
            if (updates.messages) {
              console.log(`STORE DEBUG: Updating with ${updates.messages.length} messages`);
            }
          }
          
          const updatedConversations = state.conversations.map((conv) => {
            if (conv.id === id) {
              // Only update the timestamp automatically if messages are changed
              // and no explicit updatedAt is provided
              const shouldUpdateTimestamp = 
                updates.messages !== undefined && 
                updates.updatedAt === undefined;
              
              return { 
                ...conv, 
                ...updates, 
                // Use provided timestamp or update it if messages changed
                updatedAt: updates.updatedAt || (shouldUpdateTimestamp ? new Date() : conv.updatedAt)
              };
            }
            return conv;
          });
          
          return {
            conversations: updatedConversations,
          };
        });
        
        // Check if update worked
        const afterState = get();
        const updatedConv = afterState.conversations.find(conv => conv.id === id);
        
        if (updatedConv && updates.messages) {
          console.log(`STORE DEBUG: After update, conversation ${id} has ${updatedConv.messages.length} messages`);
        }
      },
      
      deleteConversation: (id) => {
        set((state) => {
          const newConversations = state.conversations.filter((conv) => conv.id !== id);
          const newCurrentId = state.currentConversationId === id
            ? (newConversations.length > 0 ? newConversations[0].id : null)
            : state.currentConversationId;
            
          return {
            conversations: newConversations,
            currentConversationId: newCurrentId,
          };
        });
      },
      
      clearAllConversations: () => {
        set({
          conversations: [],
          currentConversationId: null
        });
      },
      
      setCurrentConversationId: (id) => set({ currentConversationId: id }),
      
      // Message actions
      addMessage: (conversationId, message) => {
        console.log('⚡ conversationStore.addMessage called with:', {
          conversationId,
          message: {
            id: message.id,
            role: message.role,
            contentPreview: typeof message.content === 'string' ? 
              message.content.substring(0, 50) + '...' : 
              '[complex content]'
          }
        });
        
        // Find the conversation
        const conversations = get().conversations;
        const conversationIndex = conversations.findIndex(c => c.id === conversationId);
        
        if (conversationIndex === -1) {
          console.error(`❌ Conversation ${conversationId} not found in store when trying to add message. Current conversations:`, 
                       conversations.map(c => c.id).join(', '));
          return null;
        }
        
        console.log(`✅ Found conversation at index ${conversationIndex}, current message count:`, 
                   conversations[conversationIndex].messages.length);
        
        // Create new message with required fields
        const newMessage: Message = {
          id: message.id || uuidv4(),
          content: message.content || '',
          role: message.role || 'user',
          timestamp: message.timestamp || new Date(),
          ...(message.metadata && { metadata: message.metadata }),
          ...(message.files && { files: message.files }),
        };
        
        // Update the store
        set(state => {
          const updatedConversations = [...state.conversations];
          const updatedMessages = [...updatedConversations[conversationIndex].messages, newMessage];
          
          updatedConversations[conversationIndex] = {
            ...updatedConversations[conversationIndex],
            messages: updatedMessages,
            updatedAt: new Date()
          };
          
          console.log(`✅ Updated conversation ${conversationId}, new message count:`, updatedMessages.length);
          
          return {
            conversations: updatedConversations
          };
        });
        
        return newMessage.id;
      },
      
      updateMessage: (conversationId, messageId, updates) => {
        set((state) => ({
          conversations: state.conversations.map((conv) =>
            conv.id === conversationId
              ? {
                  ...conv,
                  messages: conv.messages.map((msg) =>
                    msg.id === messageId
                      ? { ...msg, ...updates }
                      : msg
                  ),
                  updatedAt: new Date(),
                }
              : conv
          ),
        }));
      },
      
      updateFileAttachmentStatus: (conversationId, messageId, fileId, status, errorMessage) => {
        set((state) => ({
          conversations: state.conversations.map((conv) => {
            if (conv.id !== conversationId) return conv;

            // Found the conversation, now map messages
            return {
              ...conv,
              messages: conv.messages.map((msg) => {
                if (msg.id !== messageId || !msg.files) return msg;

                // Found the message, now map attachments
                return {
                  ...msg,
                  files: msg.files.map((file) => {
                    if (file.id !== fileId) return file;

                    // Found the attachment, update its status
                    console.log(`STORE: Updating attachment ${fileId} in msg ${messageId} to status: ${status}`);
                    return {
                      ...file,
                      status: status,
                      isUploading: status === 'uploading' || status === 'processing',
                      hasError: status === 'error',
                      errorMessage: status === 'error' ? errorMessage : undefined,
                    };
                  }),
                };
              }),
              // Optionally update conversation timestamp if needed
              // updatedAt: new Date(), 
            };
          }),
        }));
      },
      
      deleteMessage: (conversationId, messageId) => {
        set((state) => ({
          conversations: state.conversations.map((conv) =>
            conv.id === conversationId
              ? {
                  ...conv,
                  messages: conv.messages.filter((msg) => msg.id !== messageId),
                  updatedAt: new Date(),
                }
              : conv
          ),
        }));
      },
      
      // Pagination actions
      prependMessages: (conversationId, messagesToPrepend, newPaginationState) => {
        console.log(`⚡ conversationStore.prependMessages called for ${conversationId} with ${messagesToPrepend.length} messages`);
        set(state => {
          const updatedConversations = state.conversations.map(conv => {
            if (conv.id === conversationId) {
              console.log(`  Prepending to conversation with ${conv.messages.length} existing messages.`);
              // Filter out any messages that might already exist (e.g., from overlapping fetches)
              const existingMessageIds = new Set(conv.messages.map(m => m.id));
              const uniqueMessagesToPrepend = messagesToPrepend.filter(m => !existingMessageIds.has(m.id));
              
              return {
                ...conv,
                // Prepend new messages, ensure they are sorted correctly if needed
                messages: [...uniqueMessagesToPrepend, ...conv.messages],
                pagination: { // Update pagination state
                   ...(conv.pagination || {}), // Keep existing state
                   ...newPaginationState // Apply new state
                },
                // Optionally update 'updatedAt', though maybe not necessary for loading older messages?
                // updatedAt: new Date() 
              };
            }
            return conv;
          });
          return { conversations: updatedConversations };
        });

        // Debug log after update
        const updatedConv = get().conversations.find(c => c.id === conversationId);
        console.log(`  After prepend, conversation ${conversationId} has ${updatedConv?.messages.length} messages.`);
        console.log(`  New pagination state:`, updatedConv?.pagination);
      },

      setConversationPagination: (conversationId, paginationUpdates) => {
        console.log(`⚡ conversationStore.setConversationPagination called for ${conversationId}`);
        set(state => ({
          conversations: state.conversations.map(conv => {
            if (conv.id === conversationId) {
              // Ensure defaults are provided when merging partial updates
              const existingPagination = conv.pagination || { 
                isLoadingMore: false, 
                hasMoreMessages: true, 
                oldestMessageId: null 
              };
              return {
                ...conv,
                pagination: {
                  // Explicitly check if the update exists, otherwise use existing value
                  isLoadingMore: paginationUpdates.isLoadingMore !== undefined 
                                 ? paginationUpdates.isLoadingMore 
                                 : existingPagination.isLoadingMore,
                  hasMoreMessages: paginationUpdates.hasMoreMessages !== undefined 
                                   ? paginationUpdates.hasMoreMessages 
                                   : existingPagination.hasMoreMessages,
                  oldestMessageId: paginationUpdates.oldestMessageId !== undefined 
                                 ? paginationUpdates.oldestMessageId 
                                 : existingPagination.oldestMessageId,
                }
              };
            }
            return conv;
          })
        }));
      },
      
      // Loading state
      setLoading: (isLoading) => set({ isLoading }),
      setError: (error) => set({ error }),
      
      // Helpers
      getCurrentConversation: () => {
        const { conversations, currentConversationId } = get();
        return conversations.find((conv) => conv.id === currentConversationId) || null;
      },
      
      // COMMENTED OUT: This method is unused and creates local-only conversations
      // that don't sync to server properly. Use conversation.createConversation() instead.
      // createNewConversation: () => {
      //   const id = uuidv4();
      //   get().addConversation({
      //     id,
      //     title: 'New Conversation',
      //     messages: [
      //       {
      //         id: uuidv4(),
      //         content: 'Hi there! How can I help you today?',
      //         role: 'assistant',
      //         timestamp: new Date(),
      //         metadata: {}
      //       }
      //     ],
      //     createdAt: new Date(),
      //     updatedAt: new Date(),
      //     isActive: true,
      //   });
      //   return id;
      // },
      
      // Debug/Reset methods
      resetStore: () => {
        console.log('[Store] Resetting conversation store to initial state');
        // Remove current user's storage
        if (currentUserId) {
          localStorage.removeItem(`denker-conversations-storage-${currentUserId}`);
        }
        // Also remove old non-user-specific storage for migration
        localStorage.removeItem('denker-conversations-storage');
        set({
          conversations: [],
          currentConversationId: null,
          isLoading: false,
          error: null,
        });
      },
      
      // User management methods
      switchUser: (userId: string | null) => {
        console.log('[Store] Switching user from', currentUserId, 'to', userId);
        if (currentUserId !== userId) {
          currentUserId = userId;
          // Clear current state when switching users
          set({
            conversations: [],
            currentConversationId: null,
            isLoading: false,
            error: null,
          });
          // Trigger rehydration for new user
          if (userId) {
            // This will be handled by the persistence middleware automatically
            console.log('[Store] User switched, will load data for user:', userId);
          }
        }
      },
      
      getCurrentUserId: () => currentUserId,
      
      repairConversation: (id: string) => {
        console.log(`[Store] Attempting to repair conversation ${id}`);
        const state = get();
        const conversation = state.conversations.find(c => c.id === id);
        
        if (!conversation) {
          console.log(`[Store] Conversation ${id} not found, cannot repair`);
          return false;
        }
        
        // Fix any corrupted data
        const repairedConversation = {
          ...conversation,
          messages: conversation.messages.map(msg => ({
            ...msg,
            timestamp: msg.timestamp instanceof Date ? msg.timestamp : new Date(msg.timestamp),
            content: msg.content || '',
            role: msg.role || 'user',
            id: msg.id || uuidv4(),
          })),
          createdAt: conversation.createdAt instanceof Date ? conversation.createdAt : new Date(conversation.createdAt),
          updatedAt: conversation.updatedAt instanceof Date ? conversation.updatedAt : new Date(conversation.updatedAt),
        };
        
        // Update the conversation
        set(state => ({
          conversations: state.conversations.map(c => 
            c.id === id ? repairedConversation : c
          )
        }));
        
        console.log(`[Store] Repaired conversation ${id}`);
        return true;
      },
    }),
    {
      name: () => currentUserId ? `denker-conversations-storage-${currentUserId}` : 'denker-conversations-storage-temp', // user-specific storage key
      storage: createJSONStorage(() => localStorage), // use localStorage by default
      partialize: (state) => {
        console.log('Persisting conversation state with', state.conversations.length, 'conversations');
        // Only store conversations and current ID, not loading states
        return {
          conversations: state.conversations,
          currentConversationId: state.currentConversationId,
        };
      },
      // Handle date serialization/deserialization
      onRehydrateStorage: () => (state) => {
        console.log('PERSIST: Rehydrating conversation store...');
        
        if (!state) {
          console.log('PERSIST: No state found in storage');
          return;
        }
        
        console.log('PERSIST: Found state with', 
          state.conversations ? state.conversations.length : 0, 'conversations');
        
        // Convert date strings back to Date objects after rehydration
        if (state && state.conversations) {
          console.log('PERSIST: Converting date strings to Date objects');
          try {
            const fixedConversations = state.conversations.map(conv => {
              console.log(`PERSIST: Processing conversation ${conv.id} with ${conv.messages.length} messages`);
              return {
                ...conv,
                createdAt: new Date(conv.createdAt),
                updatedAt: new Date(conv.updatedAt),
                messages: conv.messages.map(msg => ({
                  ...msg,
                  timestamp: new Date(msg.timestamp)
                }))
              };
            });
            state.conversations = fixedConversations;
            console.log('PERSIST: Successfully converted all dates');
          } catch (error) {
            console.error('PERSIST: Error during date conversion:', error);
          }
        }
        
        console.log('PERSIST: Conversation store rehydration complete');
      }
    }
  )
);

// Log the initial state for debugging
console.log('Initial conversation store state:', useConversationStore.getState());

export default useConversationStore; 