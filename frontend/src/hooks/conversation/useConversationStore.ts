import React from 'react';

// Get current conversation
const useCurrentConversation = () => {
  const currentConversationId = useConversationStore(state => state.currentConversationId);
  const conversations = useConversationStore(state => state.conversations);
  
  return React.useMemo(() => {
    if (!currentConversationId) return null;
    return conversations.find(c => c.id === currentConversationId) || null;
  }, [currentConversationId, conversations]);
};

export {
  useConversationStore,
  useCurrentConversation,
  saveConversationToDatabase,
  saveMessageToDatabase,
  loadConversationsFromDatabase
}; 