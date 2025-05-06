import { create } from 'zustand';

interface AgentStatusState {
  statusText: string | null;
  statusType: string | null; // Keep type flexible 
  agentName: string | null; // Added agentName
  workflowType: string | null; // Added workflowType
  setStatus: (text: string | null, type: string | null, agentName?: string | null) => void;
  setWorkflowType: (type: string | null) => void; // Added setter
}

const useAgentStatusStore = create<AgentStatusState>((set) => ({
  statusText: null,
  statusType: null,
  agentName: null, // Added agentName
  workflowType: null, // Added workflowType initial state
  // Updated setStatus signature
  setStatus: (text, type, agentName = null) => set((state) => ({
    statusText: text,
    statusType: type,
    agentName: agentName,
    // Clear workflow type when main status clears, unless it's being set by decision
    workflowType: text === null ? null : state.workflowType, 
  })), 
  setWorkflowType: (type) => set({ workflowType: type }), // Added setter implementation
}));

export default useAgentStatusStore; 