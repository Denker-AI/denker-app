/**
 * Debugging utilities for conversation loading issues
 */

import useConversationStore from '../store/conversationStore';
import useFileStore from '../store/fileStore';

export interface ConversationDiagnostics {
  conversationId: string;
  title: string;
  messageCount: number;
  hasMessages: boolean;
  hasFileAttachments: boolean;
  corruptedMessages: Array<{
    messageId: string;
    issues: string[];
  }>;
  storeState: {
    existsInStore: boolean;
    hasEmptyMessages: boolean;
    lastUpdated: Date | null;
  };
  fileStoreIssues: Array<{
    messageId: string;
    missingFileIds: string[];
  }>;
}

/**
 * Diagnose a specific conversation for loading issues
 */
export const diagnoseConversation = (conversationId: string): ConversationDiagnostics => {
  const conversationStore = useConversationStore.getState();
  const fileStore = useFileStore.getState();
  
  const conversation = conversationStore.conversations.find(c => c.id === conversationId);
  
  if (!conversation) {
    return {
      conversationId,
      title: 'NOT FOUND',
      messageCount: 0,
      hasMessages: false,
      hasFileAttachments: false,
      corruptedMessages: [],
      storeState: {
        existsInStore: false,
        hasEmptyMessages: false,
        lastUpdated: null,
      },
      fileStoreIssues: [],
    };
  }

  const corruptedMessages: Array<{messageId: string; issues: string[]}> = [];
  const fileStoreIssues: Array<{messageId: string; missingFileIds: string[]}> = [];
  let hasFileAttachments = false;

  // Check each message for corruption
  conversation.messages.forEach(msg => {
    const issues: string[] = [];
    
    // Check basic message integrity
    if (!msg.id) issues.push('Missing message ID');
    if (!msg.content && msg.content !== '') issues.push('Missing content');
    if (!msg.role) issues.push('Missing role');
    if (!msg.timestamp) issues.push('Missing timestamp');
    if (msg.timestamp && !(msg.timestamp instanceof Date)) issues.push('Invalid timestamp type');
    
    // Check file attachment issues
    const fileIds = msg.metadata?.file_ids || [];
    if (fileIds.length > 0) {
      hasFileAttachments = true;
      const missingFileIds: string[] = [];
      
      fileIds.forEach((fileId: string) => {
        const fileExists = fileStore.files.some(f => f.id === fileId);
        if (!fileExists) {
          missingFileIds.push(fileId);
        }
      });
      
      if (missingFileIds.length > 0) {
        fileStoreIssues.push({
          messageId: msg.id,
          missingFileIds,
        });
      }
      
      // Check if files property is missing despite having file_ids
      if (!msg.files || msg.files.length === 0) {
        issues.push('Has file_ids but missing files property');
      }
    }
    
    if (issues.length > 0) {
      corruptedMessages.push({
        messageId: msg.id,
        issues,
      });
    }
  });

  return {
    conversationId,
    title: conversation.title,
    messageCount: conversation.messages.length,
    hasMessages: conversation.messages.length > 0,
    hasFileAttachments,
    corruptedMessages,
    storeState: {
      existsInStore: true,
      hasEmptyMessages: conversation.messages.length === 0,
      lastUpdated: conversation.updatedAt,
    },
    fileStoreIssues,
  };
};

/**
 * Diagnose all conversations and return problematic ones
 */
export const diagnoseAllConversations = (): ConversationDiagnostics[] => {
  const conversationStore = useConversationStore.getState();
  
  return conversationStore.conversations.map(conv => 
    diagnoseConversation(conv.id)
  );
};

/**
 * Get conversations that never load (have issues)
 */
export const getProblematicConversations = (): ConversationDiagnostics[] => {
  return diagnoseAllConversations().filter(diag => 
    diag.corruptedMessages.length > 0 || 
    diag.fileStoreIssues.length > 0 || 
    !diag.hasMessages
  );
};

/**
 * Clear localStorage and reset all stores (nuclear option)
 */
export const resetAllConversationData = (): void => {
  console.warn('[Debug] Resetting all conversation data');
  
  // Clear localStorage
  localStorage.removeItem('denker-conversations-storage');
  localStorage.removeItem('denker-file-storage');
  
  // Reset stores
  const conversationStore = useConversationStore.getState();
  if (conversationStore.resetStore) {
    conversationStore.resetStore();
  }
  
  console.log('[Debug] All conversation data reset');
};

/**
 * Log detailed diagnostics for debugging
 */
export const logConversationDiagnostics = (conversationId?: string): void => {
  if (conversationId) {
    const diag = diagnoseConversation(conversationId);
    console.group(`🔍 Conversation Diagnostics: ${conversationId}`);
    console.log('Title:', diag.title);
    console.log('Message Count:', diag.messageCount);
    console.log('Has Messages:', diag.hasMessages);
    console.log('Has File Attachments:', diag.hasFileAttachments);
    console.log('Store State:', diag.storeState);
    
    if (diag.corruptedMessages.length > 0) {
      console.warn('Corrupted Messages:', diag.corruptedMessages);
    }
    
    if (diag.fileStoreIssues.length > 0) {
      console.warn('File Store Issues:', diag.fileStoreIssues);
    }
    
    console.groupEnd();
  } else {
    const allDiagnostics = diagnoseAllConversations();
    const problematic = getProblematicConversations();
    
    console.group('🔍 All Conversation Diagnostics');
    console.log(`Total Conversations: ${allDiagnostics.length}`);
    console.log(`Problematic Conversations: ${problematic.length}`);
    
    if (problematic.length > 0) {
      console.warn('Problematic Conversations:', problematic);
    }
    
    allDiagnostics.forEach(diag => {
      if (diag.corruptedMessages.length > 0 || diag.fileStoreIssues.length > 0 || !diag.hasMessages) {
        console.warn(`❌ ${diag.conversationId} (${diag.title}):`, {
          messages: diag.messageCount,
          corrupted: diag.corruptedMessages.length,
          fileIssues: diag.fileStoreIssues.length,
        });
      } else {
        console.log(`✅ ${diag.conversationId} (${diag.title}): ${diag.messageCount} messages`);
      }
    });
    
    console.groupEnd();
  }
};

// Make debugging functions available globally in development
if (typeof window !== 'undefined' && process.env.NODE_ENV === 'development') {
  (window as any).conversationDebug = {
    diagnose: diagnoseConversation,
    diagnoseAll: diagnoseAllConversations,
    getProblematic: getProblematicConversations,
    reset: resetAllConversationData,
    log: logConversationDiagnostics,
  };
  
  console.log('🔧 Conversation debug tools available at window.conversationDebug');
} 