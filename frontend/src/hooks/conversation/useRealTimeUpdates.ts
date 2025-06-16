import { useEffect, useCallback, useState, useRef } from 'react';
import { v4 as uuidv4 } from 'uuid';
import useAgentWebSocket from '../../services/agentWebSocket';
import useConversationStore from '../../store/conversationStore';
import { useEnhancedApi } from '../api';
import useMessageDatabaseUtils from './messageDatabaseUtils';
import { FileAttachment } from './types';

// Import the AgentStepType directly
import type { AgentStepType } from '../../services/agentWebSocket';
// Import the new status store hook
import useAgentStatusStore from '../../store/agentStatusStore';

// Define the interface for human input requests
export interface HumanInputRequest {
  inputId: string;
  toolName: string;
  inputPrompt: string;
  toolDescription?: string;
  queryId: string;
  conversationId: string;
}

// --- ADDED: Simpler Per-Conversation State --- 
interface ConversationSpecificState {
  isLoading: boolean;
  humanInputRequest: HumanInputRequest | null;
  isWaitingForClarification: boolean; // Track clarification state simply
}
// --- END ADDED ---

// ADDED: Utility function to map technical agent names to user-friendly display names
const getUserFriendlyAgentName = (technicalName: string): string => {
  // ADDED: Input validation
  if (!technicalName || typeof technicalName !== 'string') {
    console.warn(`[getUserFriendlyAgentName] Invalid input: "${technicalName}"`);
    return 'Agent'; // Fallback for invalid input
  }
  // --- END ADDED ---
  
  console.log(`[getUserFriendlyAgentName] Input: "${technicalName}"`);
  
  // ADDED: Handle MCP agent namespace pattern first
  // Pattern: mcp_agent.workflows.llm.augmented_llm_anthropic.{agent_name}
  if (technicalName.includes('mcp_agent.workflows.llm.augmented_llm_anthropic.')) {
    const agentName = technicalName.split('.').pop(); // Get the last part after the dots
    console.log(`[getUserFriendlyAgentName] Detected MCP namespace, extracted: "${agentName}"`);
    if (agentName && agentName !== 'SharedCacheLLMAggregator' && agentName !== 'cachesharedllm') {
      // This is our agent-specific namespace - use the agent name directly
      console.log(`[getUserFriendlyAgentName] Using extracted agent name from namespace: ${agentName}`);
      return getUserFriendlyAgentName(agentName); // Recursively map the extracted agent name
    }
  }
  // --- END ADDED ---
  
  const agentNameMappings: { [key: string]: string } = {
    // Cache and infrastructure names (fallback cases)
    'SharedCacheLLMAggregator': 'Agent', // ADDED
    'SharedCacheLLM': 'Agent',
    'SharedOrchestatorLLM': 'Orchestrator',
    'SharedOrchestrator': 'Orchestrator',
    'cachesharedllm': 'Agent', // ADDED lowercase variant
    
    // MCP agent client session
    'mcp_agent_client_session': 'Assistant',
    
    // Planner names
    'StrictLLMOrchestrationPlanner': 'Planning Assistant',
    'LLM Orchestration Planner': 'Planning Assistant',
    'LLMOrchestrationPlanner': 'Planning Assistant',
    
    // Agent wrapper names
    'AgentSpecificWrapper': 'Assistant',
    
    // Augmented LLM names
    'AugmentedLLMAnthropic': 'Agent',
    'augmented_llm_anthropic': 'Agent',
    'AugmentedLLM': 'Agent',
    'AnthropicAugmentedLLM': 'Agent',
    'FixedAnthropicAugmentedLLM': 'Agent',
    'SemaphoreGuardedLLM': 'Agent',
    
    // New consolidated agent names (4-agent system)
    'decider': 'Decision Agent',
    'researcher': 'Research Agent',
    'creator': 'Creator Agent',
    'editor': 'Editor Agent',
    
    // System names
    'router': 'Router',
    'orchestrator': 'Orchestrator',
    'system': 'System',
    'System': 'System'
  };
  
  // Direct mapping if exists
  if (agentNameMappings[technicalName]) {
    return agentNameMappings[technicalName];
  }
  
  // Handle case variations for common agent names
  const lowerName = technicalName.toLowerCase();
  for (const [key, value] of Object.entries(agentNameMappings)) {
    if (key.toLowerCase() === lowerName) {
      return value;
    }
  }
  
  // Handle names that contain keywords
  if (technicalName.toLowerCase().includes('planner')) {
    return 'Planning Assistant';
  }
  if (technicalName.toLowerCase().includes('orchestrat')) {
    return 'Orchestrator';
  }
  if (technicalName.toLowerCase().includes('cache')) {
    return 'Assistant';
  }
  if (technicalName.toLowerCase().includes('shared')) {
    return 'Assistant';
  }
  if (technicalName.toLowerCase().includes('augmented')) {
    return 'Agent';
  }
  if (technicalName.toLowerCase().includes('anthropic')) {
    return 'Agent';
  }
  
  // Clean up technical names by removing technical suffixes/prefixes
  let cleanName = technicalName
    .replace(/^(Shared|Fixed|Semaphore|Guarded|LLM|MCP|Augmented|Anthropic)/, '') // Remove technical prefixes
    .replace(/(LLM|Wrapper|Agent|Instance|Anthropic)$/, '') // Remove technical suffixes
    .trim();
  
  // If we cleaned everything away, use a fallback
  if (!cleanName) {
    cleanName = 'Agent';
  }
  
  // Capitalize first letter
  const result = cleanName.charAt(0).toUpperCase() + cleanName.slice(1);
  console.log(`[getUserFriendlyAgentName] Final result: "${technicalName}" → "${result}"`);
  return result;
};

/**
 * Hook for handling real-time updates via WebSocket.
 * Listens for incoming messages and updates the conversation store.
 */
export const useRealTimeUpdates = () => {
  // Get the enhanced API
  const { api } = useEnhancedApi();
  
  // Get conversation store actions
  const {
    currentConversationId: viewedConversationId, // Renamed for clarity
    addMessage,
    conversations,
    deleteMessage,
    updateFileAttachmentStatus
  } = useConversationStore();
  
  // Get database utilities
  const { saveMessageToDatabase } = useMessageDatabaseUtils();
  
  // Get the agent status store actions
  const { setStatus: setAgentStatus, setWorkflowType } = useAgentStatusStore();
  
  // --- State Refactoring --- 
  // Global WebSocket/Query Tracking
  const [activeQueryId, setActiveQueryId] = useState<string | null>(null); // Tracks the queryId the WS is connected for
  const [globalProcessingState, setGlobalProcessingState] = useState<boolean>(false); // Tracks if the WS connection is active
  const [processingQueries, setProcessingQueries] = useState<Record<string, string>>({}); // Map: queryId -> conversationId
  const processingQueriesRef = useRef(processingQueries);
  useEffect(() => {
    processingQueriesRef.current = processingQueries;
  }, [processingQueries]);

  // Per-Conversation State
  const [perConversationState, setPerConversationState] = useState<Record<string, ConversationSpecificState>>({});

  // --- ADDED: Streaming state for handling word-by-word messages ---
  const [streamingMessages, setStreamingMessages] = useState<Map<string, string>>(new Map());
  const [streamingMessageIds, setStreamingMessageIds] = useState<Map<string, string>>(new Map()); // Maps streaming key to message ID
  // --- END ADDED ---

  // REMOVED: Old individual state variables
  // const [isAnyQueryProcessing, setIsAnyQueryProcessing] = useState<boolean>(false);
  // const [humanInputRequest, setHumanInputRequest] = useState<HumanInputRequest | null>(null);
  // const [decisionState, setDecisionState] = useState<{...}>({...});
  // --- End State Refactoring --- 

  // Use a ref to track the last step data to prevent unnecessary re-renders
  const lastStepDataRef = useRef<any>(null);

  // Ref to track query IDs whose final response has been added
  const processedQueryIdsRef = useRef<Set<string>>(new Set());

  // 1. connectToWebSocket (No internal dependencies on other callbacks here)
  const connectToWebSocket = useCallback((queryId: string, conversationId: string) => {
    // --- ADDED: Log entry point --- 
    console.log(`[useRealTimeUpdates] connectToWebSocket ENTERED for query ${queryId} in conversation ${conversationId}`);
    // --- END ADDED ---
    if (!queryId) {
      console.error('🔴 No query ID provided');
      return;
    }
    if (!conversationId) {
      console.error('🔴 No conversation ID provided');
      return;
    }
    console.log(`🟢 Setting up WebSocket tracking for query ${queryId} in conversation ${conversationId}`);
    console.log(`🟢 Query ID format: ${queryId.substring(0, 15)}... (${queryId.length} chars)`);
    setGlobalProcessingState(true); // Mark as processing
    setActiveQueryId(queryId);
    setProcessingQueries(prev => ({ ...prev, [queryId]: conversationId }));
    // --- MODIFIED: Initialize simpler state --- 
    setPerConversationState(prev => ({
      ...prev,
      [conversationId]: { 
        isLoading: true,
        humanInputRequest: null,
        isWaitingForClarification: false // Initialize flag
      }
    }));
    // --- END MODIFIED ---
    console.log(`🟢 WebSocket connection details: 
      - Query ID: ${queryId}
      - Conversation ID: ${conversationId}
      - Timestamp: ${new Date().toISOString()}
    `);
  }, []); // Dependencies: none from this group

  // 2. Handle WebSocket hook - needs to be called to get closeWebSocket for cleanupQueryResources
  const { 
    isConnected: wsConnected, 
    streamingSteps,
    status: wsStatus,
    mcpData,
    latestStepData,
    hasActiveWebSocketForQuery,
    closeWebSocket // Get the function here
  } = useAgentWebSocket(activeQueryId || '', processingQueries[activeQueryId || '']);

  // 3. cleanupQueryResources (Depends on closeWebSocket from hook above)
  const cleanupQueryResources = useCallback((queryId: string) => {
    if (!queryId) return;
    console.log(`🧹 Cleaning up resources for completed query: ${queryId}`);
    
    // Check if it's actually processing before cleaning (to prevent double cleanup calls)
    if (!processingQueriesRef.current[queryId]) {
      console.log(`🧹 Query ${queryId} already cleaned up or not found in ref, skipping cleanup.`);
      return; 
    }

    if (closeWebSocket && typeof closeWebSocket === 'function') {
      const closed = closeWebSocket(queryId);
      if (closed) console.log(`🧹 Successfully closed WebSocket for query: ${queryId}`);
    }
    
    if (activeQueryId === queryId) {
      setActiveQueryId(null);
      // --- ADDED: Explicitly turn off loading indicator when the ACTIVE query is cleaned up ---
      setGlobalProcessingState(false);
      // --- END ADDED ---
    }
    // --- RE-ENABLE setProcessingQueries ---
    // /*
    setProcessingQueries(prev => {
      const updated = { ...prev };
      // --- MODIFIED: Find conversationId FIRST --- 
      const conversationId = processingQueriesRef.current[queryId];
      if (updated[queryId]) delete updated[queryId];
      // --- END MODIFIED ---
      // Update ref immediately inside setState callback for consistency
      processingQueriesRef.current = updated; 
      if (Object.keys(updated).length === 0) setGlobalProcessingState(false);

      // --- MODIFIED: Update simpler state --- 
      if (conversationId) {
        setPerConversationState(prevState => ({
          ...prevState,
          [conversationId]: {
            ...(prevState[conversationId] || { isLoading: false, humanInputRequest: null, isWaitingForClarification: false }),
            isLoading: false, // Mark loading as false for this conversation
            humanInputRequest: null, // Clear input request
            isWaitingForClarification: false // Reset clarification flag
          }
        }));
      } else {
        console.warn(`[cleanupQueryResources] Could not find conversationId for query ${queryId} in processingQueriesRef.`);
      }
      // --- END MODIFIED ---
      return updated;
    });
    // */
    // console.log(`🧹 SKIPPING setProcessingQueries in cleanup for query ${queryId}`);
    // --- END RE-ENABLE ---
    if (lastStepDataRef.current && lastStepDataRef.current.queryId === queryId) {
      lastStepDataRef.current = null;
    }
    
    // --- RE-ENABLED: Clear agent status on cleanup --- 
    setAgentStatus(null, null); 
    // REMOVED: setWorkflowType(null); // Let the 'Finished' step handler clear this
    // --- END RE-ENABLED ---
  }, [activeQueryId, closeWebSocket, setAgentStatus, setWorkflowType]); // Keep dependencies

  // 4. processFinalResponse (Depends on cleanupQueryResources)
  const processFinalResponse = useCallback(async (responseData: any, conversationId: string, queryId?: string) => {
    const doCleanup = () => { if (queryId) cleanupQueryResources(queryId); };
    // --- Log Entry ---
    console.log(
        `🟨 processFinalResponse ENTERED. Query ID: ${queryId}. Conversation ID: ${conversationId}. Processed Set: ${JSON.stringify(Array.from(processedQueryIdsRef.current))}`
    );
    // --- END Log ---
    
    // --- Check if already processed --- 
    const alreadyProcessed = queryId ? processedQueryIdsRef.current.has(queryId) : false;
    console.log(`🟨 processFinalResponse - Already Processed Check for ${queryId}: ${alreadyProcessed}`); // ADDED LOG
    if (alreadyProcessed) {
        console.warn(`🟨 Query ${queryId} final response already processed. Skipping duplicate addition.`);
        doCleanup(); // Ensure cleanup even if skipping
        return null;
    }
    // --- END Check ---

    // *** Use the ref for the check ***
    // MOVED Check: If already processed, we return above.
    // *******************************

    // --- ADDED Safety Check --- 
    if (!responseData) {
        console.warn('🟢 processFinalResponse called with null or undefined responseData');
        doCleanup(); 
        return null;
    }
    // --- END Safety Check --- 

    try {
      if (responseData && responseData.result) {
        let rawResultText = responseData.result;
        // --- Handle non-string results first ---
        if (typeof rawResultText !== 'string') {
           if (rawResultText && rawResultText.text) rawResultText = rawResultText.text;
           else if (rawResultText && rawResultText.message) rawResultText = rawResultText.message;
           else try { rawResultText = JSON.stringify(rawResultText); } catch (err) { rawResultText = '[Non-string result]'; }
        }
        // --- END Handle non-string ---

        // Backend now handles result cleaning, so we just use the result as-is
        console.log(`[Result Parse] Using backend-cleaned result (first 200 chars): "${rawResultText.substring(0, 200)}..."`);
        let formattedContent = rawResultText.trim(); 
        
        const messageId = `response_${Date.now()}_${uuidv4().substring(0, 5)}`;
        const targetConversationId = conversationId; 
        const loadingMessageId = `loading_${targetConversationId}`;
        try { deleteMessage(targetConversationId, loadingMessageId); } catch (err) { /* ignore */ }
        
        // Prepare metadata safely
        const metadata: Record<string, any> = { queryId: queryId };
        if (responseData.workflowType) metadata.workflowType = responseData.workflowType;
        if (responseData.explanation) metadata.explanation = responseData.explanation;
        if (responseData.needsClarification) metadata.needsClarification = responseData.needsClarification;
        if (responseData.clarifyingQuestions) metadata.clarifyingQuestions = responseData.clarifyingQuestions;
        
        // --- ADDED: Mark as processed BEFORE adding message --- 
        if (queryId) {
            processedQueryIdsRef.current.add(queryId);
            console.log(`🟨 Marked query ${queryId} as processed in Ref.`);
        }
        // --- END ADDED ---
        
        console.log(`🟨 processFinalResponse - BEFORE addMessage for Query ID: ${queryId}, Message ID: ${messageId}`);
        await addMessage(targetConversationId, {
          id: messageId, content: formattedContent, role: 'assistant', timestamp: new Date(), metadata // Use safe metadata
        });
        await saveMessageToDatabase(targetConversationId, uuidv4(), formattedContent, 'assistant', metadata); // Use targetConversationId
        console.log('🟨 Message added successfully by processFinalResponse');
        
        doCleanup(); // Cleanup AFTER successful processing
        return messageId;
      } else { 
          console.warn('🟢 Response data does not contain result field or responseData was null');
          doCleanup();
          return null;
      }
    } catch (err) {
        console.error('🟢 Error handling coordinator response:', err);
        doCleanup(); // Cleanup on error
        throw err; // Re-throw error so the .catch in useEffect works
    }
  }, [addMessage, saveMessageToDatabase, deleteMessage, cleanupQueryResources]);

  // 5. handleCoordinatorResponse (Depends on connectToWebSocket, processFinalResponse, cleanupQueryResources)
  const handleCoordinatorResponse = useCallback(async (responseData: any, conversationId: string) => {
    console.log('🟢 handleCoordinatorResponse CALLED');
    if (!responseData || !conversationId) {
      setGlobalProcessingState(false);
      return null;
    }
    const queryId = responseData.query_id;
    if (responseData.status === 'processing' && queryId) {
      // Check if already processing this queryId (edge case)
      if(processingQueriesRef.current[queryId]) {
         console.warn(`handleCoordinatorResponse called for already processing query ${queryId}. Ignoring.`);
         return null;
      }
      setGlobalProcessingState(true);
      setProcessingQueries(prev => ({ ...prev, [queryId]: conversationId }));
      connectToWebSocket(queryId, conversationId);
      if (responseData.result) {
        // Process immediate result *before* starting polling
        const result = await processFinalResponse(responseData, conversationId, queryId);
        // Cleanup *after* processing
        cleanupQueryResources(queryId);
        return result;
      }
      // Start polling only if no immediate result
      const pollInterval = setInterval(async () => {
        // Check if query is still active before polling
        if (!processingQueriesRef.current[queryId]) {
          console.log(`Polling stopped for ${queryId} as it is no longer processing.`);
          clearInterval(pollInterval);
          return;
        }
        try {
          // --- MODIFIED: Use the enhanced method with retry and add type assertion --- 
          const statusResponse = await api.checkCoordinatorStatusWithRetry(queryId) as {
            data: {
              status: 'processing' | 'completed' | 'error';
              message?: string;
              result?: any; // Add result field as it's used later
            }
          };
          // --- END MODIFICATION ---
          // Check again if query is still active after await
          if (!processingQueriesRef.current[queryId]) {
             console.log(`Polling stopped for ${queryId} after API call.`);
             clearInterval(pollInterval);
             return;
          }
          if (statusResponse.data.status === 'completed') {
            clearInterval(pollInterval);
            let resultData = statusResponse.data;
            if (resultData.result && typeof resultData.result === 'object') { resultData = { ...resultData, result: resultData.result.result || resultData.result }; }
            // --- ADDED: Log before poll call --- 
            console.log(`📞 Calling processFinalResponse from POLLING for query: ${queryId}`);
            // --- END ADDED ---
            await processFinalResponse(resultData, conversationId, queryId);
            cleanupQueryResources(queryId);
          } else if (statusResponse.data.status === 'error') {
            console.error(`Polling found error for query ${queryId}:`, statusResponse.data.message || 'Unknown error');
            clearInterval(pollInterval);
            cleanupQueryResources(queryId);
          }
        } catch (err) {
          console.error(`Error during polling for query ${queryId}:`, err);
          // Check if query is still active before cleaning up due to poll error
          if (processingQueriesRef.current[queryId]) {
             cleanupQueryResources(queryId);
          }
          clearInterval(pollInterval);
        }
      }, 1000);
      return null;
    } else if (responseData.result) {
      // Handle case where response has result but status isn't 'processing'
      setGlobalProcessingState(true); 
      // --- ADDED: Log before immediate result call --- 
      console.log(`📞 Calling processFinalResponse from IMMEDIATE RESULT for query: ${queryId}`);
      // --- END ADDED ---
      const result = await processFinalResponse(responseData, conversationId, queryId);
      if (queryId) cleanupQueryResources(queryId); 
      else setGlobalProcessingState(false); // Can't track without queryId
      return result;
    } else {
      // No result and not processing status
      setGlobalProcessingState(false);
    }
    return null;
  }, [api, connectToWebSocket, processFinalResponse, cleanupQueryResources]); 

  // Monitor WebSocket status and clean up when finished
  useEffect(() => {
    if (activeQueryId && (wsStatus === 'Finished' || wsStatus === 'Error')) {
      console.log(`🧹 WebSocket status changed to ${wsStatus}, scheduling cleanup for query ${activeQueryId}`);
      setAgentStatus(null, null);
      const cleanupTimeout = setTimeout(() => { 
        if (processingQueriesRef.current[activeQueryId]) {
          cleanupQueryResources(activeQueryId); 
        }
      }, 500);
      return () => clearTimeout(cleanupTimeout);
    }
  }, [wsStatus, activeQueryId, cleanupQueryResources, setAgentStatus]); // Added setAgentStatus dependencies

  // --- Main useEffect watching latestStepData ---
  useEffect(() => {
    // Initial checks (activeQueryId, latestStepData validity, duplicate step data)
    if (!activeQueryId || !latestStepData) return;

    // <<< ADDED: Log Raw Step Data >>>
    console.log("Raw WS Message:", JSON.stringify(latestStepData, null, 2));
    // <<< END ADDED >>>

    // --- ADDED: Check for exact same step data object/content --- 
    if (lastStepDataRef.current && JSON.stringify(lastStepDataRef.current) === JSON.stringify(latestStepData)) {
      console.log("🟠 Skipping re-processing identical step data.");
      return;
    }
    lastStepDataRef.current = latestStepData; // Update ref *after* check
    // --- END ADDED ---

    // --- Log Entry Point and Key Values ---
    console.log(`🟪 useEffect[latestStepData] RUNNING. Update Type: ${latestStepData.update_type}, Step QueryID: ${latestStepData.queryId}, Active QueryID: ${activeQueryId}`);
    // --- END ADDED ---

    const step = latestStepData;

    if (step.queryId !== activeQueryId) {
        console.warn(`🟪 Received step data for inactive query ${step.queryId}. Current active: ${activeQueryId}. Ignoring.`);
        return;
    }

    // --- Route specific updates to AgentStatusStore --- 
    const updateType = step.update_type;
    const stepType = step.step_type;
    const message = step.message; // Extract message for convenience
    const rawData = step.raw_data || {}; // Ensure rawData exists
    const conversationId = processingQueriesRef.current[activeQueryId];
    
    // --- MODIFIED: Use raw_data for stepDataPayload --- 
    const stepDataPayload = step.raw_data; // Use raw_data field
    // --- END MODIFIED ---

    // --- ADDED: Debugging log --- 
    console.log(`🟣 TRACE: step_type='${latestStepData.step_type}', update_type='${updateType}', stepDataPayload exists? ${!!stepDataPayload}`); // Added payload check

    // --- MOVED EARLIER: Handle the specific clarification update type --- 
    if (latestStepData.step_type === 'clarification' && stepDataPayload) {
        console.log("🟣 TRACE: Entering 'clarification' handler block.");
        const questions = stepDataPayload.clarifyingQuestions ?? []; 
        console.log(`✅ Received clarification step_type: Questions=${JSON.stringify(questions)}`);
        
        // --- MODIFIED: Format questions based on count --- 
        let clarificationMessage = "";
        const prefix = "To help me proceed, please clarify:";

        if (questions.length === 1) {
            clarificationMessage = `${prefix} ${questions[0]}`; // Prefix, space, question
        } else if (questions.length > 1) {
            clarificationMessage = `${prefix}\n`; // Prefix, newline
            // Join questions with just a newline, no numbering/bullets
            clarificationMessage += questions.map((q: string) => q).join("\n"); 
        } else {
            // Fallback if no questions were provided but clarification was requested
            clarificationMessage = "Could you provide more details?"; 
        }
        // --- END MODIFIED ---

        // Add this as an assistant message
        console.log(`🟣 TRACE: Adding clarification message via addMessage: Content='${clarificationMessage.substring(0, 50)}...'`);
        addMessage(conversationId, {
            id: `clarification_${Date.now()}`,
            content: clarificationMessage,
            role: 'assistant',
            timestamp: new Date(),
            metadata: { queryId: activeQueryId, isClarificationRequest: true }
        });
        // Save to DB
        saveMessageToDatabase(conversationId, uuidv4(), clarificationMessage, 'assistant', { queryId: activeQueryId, isClarificationRequest: true });

        // Update state to indicate waiting and STOP loading
        setPerConversationState(prev => ({
            ...prev,
            [conversationId]: {
                ...(prev[conversationId] || { isLoading: false, humanInputRequest: null, isWaitingForClarification: false }),
                isLoading: false,
                isWaitingForClarification: true
            }
        }));
        setAgentStatus(null, null); // Clear agent status indicator (if any)
        return; // Stop processing this step
    }
    // --- END MOVED EARLIER ---
    
    if (!conversationId) {
        // ADDED: Handle file status updates even if query seems finished
        // (Background task might complete after main flow)
        if (step.step_type === 'file_processing_wait') {
            console.log("[useRealTimeUpdates] Handling file_processing_wait:", step);
            // Use step.message if available, otherwise construct a default one using raw_data.files if present.
            const statusIndicatorMessage = step.message || `Processing: ${step.raw_data?.files?.join(', ') || 'file(s)'}...`;
            const agentNameForStatus = step.raw_data?.agent_name || step.raw_data?.agent || 'System'; // Enhanced extraction
            const friendlyAgentNameForStatus = getUserFriendlyAgentName(agentNameForStatus);
            setAgentStatus(statusIndicatorMessage, 'status', friendlyAgentNameForStatus);
            return; // Only update status indicator
        }
        if (step.step_type === 'file_processed' || step.step_type === 'file_error') {
          console.log("[useRealTimeUpdates] Received file status update (query may have finished):", step);
          const fileId = step.raw_data?.file_id;
          const status = step.step_type === 'file_processed' ? 'completed' as const : 'error' as const;
          const errorMsg = step.step_type === 'file_error' ? step.message : undefined;
          const messageIdForAttachment = step.raw_data?.messageId; 
          const targetConversationIdForAttachment = step.raw_data?.conversationId;

          // Update Agent Status Indicator
          const statusIndicatorMessage = step.message || 
            (step.step_type === 'file_processed' ? `File '${step.raw_data?.filename || fileId || 'unknown'}' processed.` :
            `Error processing file '${step.raw_data?.filename || fileId || 'unknown'}'`);
          const agentNameForStatus = step.raw_data?.agent_name || step.raw_data?.agent || 'System'; // Enhanced extraction
          const friendlyAgentNameForStatus = getUserFriendlyAgentName(agentNameForStatus);
          setAgentStatus(statusIndicatorMessage, 'status', friendlyAgentNameForStatus);

          if (fileId) {
            let convIdToUpdate = targetConversationIdForAttachment;
            if (!convIdToUpdate) {
                for (const conv of Object.values(conversations)) {
                    if (conv.messages.some(msg => msg.id === messageIdForAttachment)) {
                        convIdToUpdate = conv.id;
                        break;
                    }
                }
            }
            if (convIdToUpdate && messageIdForAttachment) {
              console.log(`[useRealTimeUpdates] Calling updateFileAttachmentStatus for file ${fileId} in message ${messageIdForAttachment} of conversation ${convIdToUpdate}`);
              updateFileAttachmentStatus(convIdToUpdate, messageIdForAttachment, fileId, status, errorMsg);
            } else {
              console.warn(`[useRealTimeUpdates] Could not determine conversation or messageId for file status update for file ${fileId}. Status not updated in attachment.`);
            }
          }
          return; 
        }
        console.warn(`Query ${activeQueryId} no longer processing, skipping progress message.`);
        return; 
    }
    
    // --- ADDED: Enhanced workflow type and agent name extraction --- 
    const extractWorkflowTypeAndAgent = (rawData: any, step: any) => {
      // Extract workflow type with multiple fallbacks
      const workflowType = rawData?.workflow_type || 
                          step?.workflow_type || 
                          rawData?.data?.workflow_type ||
                          step?.data?.workflow_type ||
                          null;
      
      // Extract agent name with multiple fallbacks
      const agentName = rawData?.agent_name || 
                       rawData?.agent || 
                       step?.agent_name || 
                       step?.agent ||
                       rawData?.data?.agent_name ||
                       rawData?.data?.agent ||
                       null;
      
      console.log(`🔍 Extracted workflow_type: ${workflowType}, agent_name: ${agentName}`);
      return { workflowType, agentName };
    };
    
    // Extract workflow type and agent name early
    const { workflowType: extractedWorkflowType, agentName: extractedAgentName } = extractWorkflowTypeAndAgent(rawData, step);
    
    // Update workflow type if available and not already set
    if (extractedWorkflowType && extractedWorkflowType !== 'unknown') {
      console.log(`🔍 Setting workflow type: ${extractedWorkflowType}`);
      setWorkflowType(extractedWorkflowType);
    }
    
    // Get friendly agent name for display
    const friendlyExtractedAgentName = extractedAgentName ? getUserFriendlyAgentName(extractedAgentName) : null;
    // --- END ADDED ---
    
    // --- ADDED: Handle streaming messages for 'result' update_type ---
    if (updateType === 'result' && rawData.streaming?.is_streaming) {
        const queryId = step.queryId;
        const streamingKey = `${queryId}_result`;
        const isStreamingFinal = rawData.streaming.is_final;
        
        // --- ADDED: Comprehensive debugging for streaming content ---
        console.log(`📡 STREAMING DEBUG - Raw step object:`, {
            step_message: step.message,
            step_message_type: typeof step.message,
            raw_data: rawData,
            streaming_info: rawData.streaming,
            full_step: step
        });
        
        // Try multiple sources for the streaming content
        let messageContent = '';
        if (step.message !== undefined && step.message !== null) {
            messageContent = String(step.message);
            console.log(`📡 Using step.message: "${messageContent}"`);
        } else if (rawData.message !== undefined && rawData.message !== null) {
            messageContent = String(rawData.message);
            console.log(`📡 Using rawData.message: "${messageContent}"`);
        } else if (rawData.result !== undefined && rawData.result !== null) {
            messageContent = String(rawData.result);
            console.log(`📡 Using rawData.result: "${messageContent}"`);
        } else {
            messageContent = '';
            console.warn(`📡 No valid message content found in streaming result!`);
        }
        // --- END ADDED ---
        
        console.log(`📡 Received streaming result: final=${isStreamingFinal}, message="${messageContent.substring(0, 50)}..."`);
        
        if (isStreamingFinal) {
            // Final streaming message - process as normal result
            console.log(`📡 Final streaming message received for query ${queryId}`);
            
            // Clear streaming state
            setStreamingMessages(prev => {
                const newMap = new Map(prev);
                newMap.delete(streamingKey);
                return newMap;
            });
            
            setStreamingMessageIds(prev => {
                const newMap = new Map(prev);
                newMap.delete(streamingKey);
                return newMap;
            });
            
            // Process as final result if not already processed
            if (queryId && !processedQueryIdsRef.current.has(queryId)) {
                console.log(`[useEffect] Processing final streaming result for query ${queryId}`);
                processFinalResponse(step.raw_data, conversationId, queryId)
                   .catch(err => {
                      console.error(`[useEffect] Error processing final streaming response for query ${queryId}:`, err);
                   }); 
            }
        } else {
            // Partial streaming message - update or create streaming message
            const existingMessageId = streamingMessageIds.get(streamingKey);
            
            if (existingMessageId) {
                // Update existing streaming message
                console.log(`📡 Updating streaming message ${existingMessageId} with partial content`);
                const updatedMessage = {
                    id: existingMessageId,
                    content: messageContent,
                    role: 'assistant' as const,
                    timestamp: new Date(),
                    metadata: {
                        queryId: activeQueryId,
                        isStreaming: true,
                        streamingKey: streamingKey,
                        workflowType: rawData.workflow_type || step.workflow_type // Add workflow type
                    }
                };
                addMessage(conversationId, updatedMessage);
            } else {
                // Create new streaming message
                const newMessageId = `streaming_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
                console.log(`📡 Creating new streaming message ${newMessageId} for key ${streamingKey}`);
                
                setStreamingMessageIds(prev => {
                    const newMap = new Map(prev);
                    newMap.set(streamingKey, newMessageId);
                    return newMap;
                });
                
                const streamingMessage = {
                    id: newMessageId,
                    content: messageContent,
                    role: 'assistant' as const,
                    timestamp: new Date(),
                    metadata: {
                        queryId: activeQueryId,
                        isStreaming: true,
                        streamingKey: streamingKey,
                        workflowType: rawData.workflow_type || step.workflow_type // Add workflow type
                    }
                };
                addMessage(conversationId, streamingMessage);
            }
            
            // Update streaming state
            setStreamingMessages(prev => {
                const newMap = new Map(prev);
                newMap.set(streamingKey, messageContent);
                return newMap;
            });
        }
        
        return; // Don't process as regular message
    }
    // --- END ADDED ---

    // --- MODIFIED: Handle 'result' step - check for duplicates and call processFinalResponse directly --- 
    if (stepType === 'result' || updateType === 'result') {
        const queryId = step.queryId;
        if (queryId && processedQueryIdsRef.current.has(queryId)) {
            // If already processed, just log and ignore this duplicate step
            console.warn(`[useEffect] Received duplicate 'result' step for already processed query ${queryId}. Ignoring.`);
        } else {
            // If it's a new 'result' step, log and call processFinalResponse directly.
            // processFinalResponse now handles adding message, marking processed, and cleanup.
            console.log(`[useEffect] Received step_type 'result' for new query ${queryId}. Calling processFinalResponse.`);
            processFinalResponse(step.raw_data || step, conversationId, queryId)
               .catch(err => {
                  // Log error from processing, cleanup should have happened inside processFinalResponse
                  console.error(`[useEffect] Error processing final response for query ${queryId}:`, err);
               }); 
        }
        // Whether duplicate or new, we return here as this step is fully handled.
        return;
    }
    // --- END MODIFICATION ---
    
    // --- ADDED: Handle Decision and Routing --- 
    if (stepType === 'decision') { 
        // --- ADDED: Log raw decision data --- 
        console.log(`[useRealTimeUpdates] Received 'decision' step. Raw Data:`, JSON.stringify(rawData));
        // --- END ADDED ---
        const workflowType = rawData?.workflow_type || 'unknown'; 
        console.log(`[useRealTimeUpdates] Storing workflowType from decision: ${workflowType}`);
        setWorkflowType(workflowType); 
        // --- ADDED: Confirm state setter called --- 
        console.log(`[useRealTimeUpdates] Called setWorkflowType with: ${workflowType}`);
        // --- END ADDED ---

        // --- MODIFIED: Handle clarification directly within the decision step if needed ---
        if (rawData?.needs_clarification === true) {
          console.log(`[useRealTimeUpdates] Decision step indicates clarification is needed. Handling directly.`);

          // Extract questions and explanation (use backend field name 'clarifying_questions')
          const questions = rawData?.clarifying_questions ?? [];
          const explanation = rawData?.explanation; // Get explanation if available

          console.log(`✅ Extracted clarification data from decision: Questions=${JSON.stringify(questions)}, Explanation=${explanation}`);

          // Format the message - Simplified as per user request
          let clarificationMessage = "";
          const prefix = "To help me proceed, please clarify:"; // Fixed prefix, explanation removed

          if (questions.length > 0) {
              clarificationMessage = `${prefix}\n`; // Prefix + newline
              clarificationMessage += questions.map((q: string) => q).join("\n"); // Join questions with newline
          } else {
              // Fallback if clarification needed but no specific questions provided
              clarificationMessage = "Could you provide more details?";
          }

          // Add the message to the chat UI
          console.log(`🟣 TRACE: Adding clarification message from 'decision' handler: Content='${clarificationMessage.substring(0, 50)}...'`);
          addMessage(conversationId, {
              id: `clarification_decision_${Date.now()}`,
              content: clarificationMessage,
              role: 'assistant',
              timestamp: new Date(),
              metadata: { queryId: activeQueryId, isClarificationRequest: true, explanation: explanation }
          });

          // Save the message to the database
          saveMessageToDatabase(conversationId, uuidv4(), clarificationMessage, 'assistant', { queryId: activeQueryId, isClarificationRequest: true, explanation: explanation });

          // Update state: Set waiting flag, stop loading indicator
          setPerConversationState(prev => ({
              ...prev,
              [conversationId]: {
                  ...(prev[conversationId] || { isLoading: false, humanInputRequest: null, isWaitingForClarification: false }),
                  isLoading: false, // Stop loading as we are waiting for input
                  isWaitingForClarification: true // Set the flag
              }
          }));

          // Clear any agent status message
          setAgentStatus(null, null);

          // Stop processing this decision message further
          return;
        }
        // --- END MODIFICATION ---

        // If it was just a decision message without clarification, just return
        return;
    }
    
    // Add log to check stepType before Routing check
    console.log(`[useRealTimeUpdates] Checking for Routing/Chatting. Current stepType: >>>${stepType}<<<`); // Added markers for clarity

    // --- MODIFIED: Convert to lowercase for case-insensitive comparison --- 
    if (stepType?.trim().toLowerCase() === 'routing') { 
        // ENHANCED: Use extracted agent name first, then fallback to step data
        const agentName = extractedAgentName || step.raw_data?.agent_name || step.raw_data?.agent || step.raw_data?.selected_agent || 'Router';
        const friendlyAgentName = friendlyExtractedAgentName || getUserFriendlyAgentName(agentName);
        const routingMsg = `Routing to ${friendlyAgentName}`; // Changed message format
        console.log(`[useRealTimeUpdates] Routing step_type 'routing' to AgentStatusIndicator: ${routingMsg} (Agent: ${friendlyAgentName}, Workflow: ${extractedWorkflowType})`);
        setAgentStatus(routingMsg, 'routing', friendlyAgentName); // Use lowercase 'routing' for consistency
        console.log("[useRealTimeUpdates] Explicit RETURN after handling routing."); 
        return;
    }
    // --- END MODIFICATION ---
    
    // --- Handle intermediate statuses --- 
    if (stepType === 'status') {
        const isConnectionMsg = message === 'WebSocket connection established' || message === 'WebSocket connection verified';
        const statusMsg = isConnectionMsg ? "Agent is connected" : message;
        console.log(`[useRealTimeUpdates] Routing step_type 'status' to AgentStatusIndicator: ${statusMsg}`); 
        setAgentStatus(statusMsg, 'status', null); 
        return; // Don't add to chat history
    }
    
    // --- ADDED: Explicit handler for 'running' step_type --- 
    if (stepType?.toLowerCase() === 'running') {
        console.log("🟣 TRACE: Entering 'running' handler block."); 
        const agentName = extractedAgentName || rawData?.agent_name || rawData?.agent || 'Agent'; // Enhanced extraction
        const friendlyAgentName = friendlyExtractedAgentName || getUserFriendlyAgentName(agentName);
        const runningMsg = `${friendlyAgentName} is running...`; 
        console.log(`[useRealTimeUpdates] Routing step_type 'running' to AgentStatusIndicator: ${runningMsg} (Workflow: ${extractedWorkflowType})`); 
        setAgentStatus(runningMsg, 'running', friendlyAgentName); // Use 'running' status type
        return; // Prevent adding to history
    }
    // --- END ADDED ---
    
    if (stepType?.toLowerCase() === 'chatting') {
        // --- MODIFIED: Enhanced agent name extraction --- 
        console.log("[useRealTimeUpdates] Raw data for Chatting step:", step.raw_data);
        const agentName = extractedAgentName || step.raw_data?.agent_name || step.raw_data?.agent || 'Agent'; // Prioritize extracted agent_name
        const friendlyAgentName = friendlyExtractedAgentName || getUserFriendlyAgentName(agentName);
        console.log(`[useRealTimeUpdates] Extracted agentName for Chatting: ${friendlyAgentName}`);
        const runningMsg = `${friendlyAgentName} is running...`; 
        console.log(`[useRealTimeUpdates] Routing step_type 'Chatting' to AgentStatusIndicator: ${runningMsg} (Workflow: ${extractedWorkflowType})`); 
        setAgentStatus(runningMsg, 'Chatting', friendlyAgentName); 
        console.log("[useRealTimeUpdates] Explicit RETURN after handling Chatting."); // Added log
        return; 
    }
    
    // Skip other meta step types that shouldn't show status or be added to history
    if (stepType === 'Finished') {
        setAgentStatus(null, null); 
        setWorkflowType(null); 
        return; 
    }
    
    // --- MODIFIED: Handle file status updates and route to AgentStatusIndicator ---\
    if (step.step_type === 'file_processing_wait') {
        console.log("[useRealTimeUpdates] Handling file_processing_wait:", step);
        // Use step.message if available, otherwise construct a default one using raw_data.files if present.
        const statusIndicatorMessage = step.message || `Processing: ${step.raw_data?.files?.join(', ') || 'file(s)'}...`;
        const agentNameForStatus = step.raw_data?.agent_name || step.raw_data?.agent || 'System'; // Enhanced extraction
        const friendlyAgentNameForStatus = getUserFriendlyAgentName(agentNameForStatus);
        setAgentStatus(statusIndicatorMessage, 'status', friendlyAgentNameForStatus);
        return; // Only update status indicator
    }
    
    if (step.step_type === 'file_processed' || step.step_type === 'file_error') {
      console.log("[useRealTimeUpdates] Handling file status update:", step);
      const fileId = step.raw_data?.file_id;
      const status = step.step_type === 'file_processed' ? 'completed'as const : 'error' as const;
      const errorMsg = step.step_type === 'file_error' ? step.message : undefined;
      const messageIdForAttachment = step.raw_data?.messageId; 

      // Update Agent Status Indicator
      const statusIndicatorMessage = step.message || 
        (step.step_type === 'file_processed' ? `File '${step.raw_data?.filename || fileId || 'unknown'}' processed.` :
        `Error processing file '${step.raw_data?.filename || fileId || 'unknown'}'`);
      const agentNameForStatus = step.raw_data?.agent_name || step.raw_data?.agent || 'System'; // Enhanced extraction
      const friendlyAgentNameForStatus = getUserFriendlyAgentName(agentNameForStatus);
      setAgentStatus(statusIndicatorMessage, 'status', friendlyAgentNameForStatus);

      // Update file attachment status in the UI if applicable
      if (fileId && conversationId && messageIdForAttachment) {
        console.log(`[useRealTimeUpdates] Calling updateFileAttachmentStatus for file ${fileId} in message ${messageIdForAttachment} of conversation ${conversationId}`);
        updateFileAttachmentStatus(conversationId, messageIdForAttachment, fileId, status, errorMsg);
      } else {
        if (!fileId) console.warn(`[useRealTimeUpdates] Missing fileId in ${step.step_type} payload.`);
        if (!messageIdForAttachment) console.warn(`[useRealTimeUpdates] Missing messageId in ${step.step_type} payload. Cannot update attachment status.`);
      }
      return; 
    }
    // --- END MODIFIED --- 

    // If we reach here, it's a progress step that SHOULD be added to the chat history
    // (e.g., Tool Calls, Tool Results, LLM Text Output)
    const messageId = `progress_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
    let content = '';
    const currentStepType = latestStepData.step_type || 'Update'; // Renamed variable

    // --- ADDED: Handle the specific clarification update type --- 
    if (latestStepData.step_type === 'clarification' && stepDataPayload) {
      const questions = stepDataPayload.clarifyingQuestions ?? ['Could you provide more details?'];
      const explanation = stepDataPayload.explanation;
      console.log(`✅ Received clarification request: Questions=${JSON.stringify(questions)}, Explanation=${explanation}`);
      setPerConversationState(prev => ({
        ...prev,
        [conversationId]: {
          ...(prev[conversationId] || { isLoading: false, humanInputRequest: null, isWaitingForClarification: false }),
          isWaitingForClarification: true
        }
      }));
      setAgentStatus(null, null); // Ensure loading indicator is off
      return; // Stop processing this message further
    }
    // --- END ADDED ---

    // --- ADDED: Handle the specific human_input update type --- 
    if (updateType === 'human_input' && stepDataPayload) {
      const inputId = stepDataPayload.input_id;
      const prompt = latestStepData.message; // Message field usually contains the prompt here
      const toolName = stepDataPayload.tool_name;
      const description = stepDataPayload.tool_description;
      
      if (!inputId) {
        console.error("🔴 Received human_input update without input_id!", latestStepData);
        setAgentStatus("Error: Internal issue requesting input.", 'error', null);
        return;
      }

      console.log(`✅ Received actual human input request: ID=${inputId}, Prompt=${prompt}`);
      // Set the state based on the dedicated human_input message
      setPerConversationState(prev => ({
        ...prev,
        [conversationId]: {
          ...(prev[conversationId] || { isLoading: false, humanInputRequest: null, isWaitingForClarification: false }),
          humanInputRequest: { 
            inputId: inputId,
            toolName: toolName,
            inputPrompt: prompt, 
            toolDescription: description, 
            queryId: activeQueryId, 
            conversationId 
          }
        }
      }));
      return; // Stop processing this message further
    }
    // --- END ADDED ---

    // <<< ADDED: Log stepType before plan check >>>
    console.log(`Checking for updateType='plan'. Current stepType is: ${stepType}`);
    // <<< END ADDED >>>

    // --- ADDED: Handle streaming messages for 'plan' update_type ---
    // DISABLED: Streaming plans to prevent duplicate plan messages
    /*
    if (updateType === 'plan' && rawData.streaming?.is_streaming) {
        const queryId = step.queryId;
        const streamingKey = `${queryId}_plan`;
        const isStreamingFinal = rawData.streaming.is_final;
        
        // --- FIXED: Generate the actual formatted plan content for streaming ---
        let messageContent = '';
        
        if (isStreamingFinal) {
            // For final streaming, generate the complete formatted plan
            const planData = step.raw_data?.plan_details;
            let planContent = "";
            
            if (planData && Array.isArray(planData.steps) && planData.steps.length > 0) {
                try {
                    const formattedSteps = planData.steps.map((planStep: any, stepIndex: number) => {
                        let stepString = `* **Step ${stepIndex + 1}:** ${planStep.description || 'No step description'}`;
                        
                        if (planStep.tasks && Array.isArray(planStep.tasks) && planStep.tasks.length > 0) {
                            const formattedTasks = planStep.tasks.map((task: any) => {
                                return `  * Task: ${task.description || 'No task description'} (Agent: ${task.agent || 'N/A'})`;
                            }).join('\n');
                            stepString += `\n${formattedTasks}`;
                        }
                        return stepString;
                    }).join('\n\n');
                    
                    planContent = formattedSteps;
                } catch (formatError) {
                    console.error("Plan streaming - Error during plan formatting:", formatError);
                    planContent = "(Error formatting plan details)";
                }
            } else if (typeof planData === 'object' && planData !== null) {
                planContent = `\`\`\`json\n${JSON.stringify(planData, null, 2)}\n\`\`\``;
            } else if (typeof planData === 'string') {
                planContent = `\`\`\`\n${planData}\n\`\`\``;
            } else {
                planContent = "(Plan details not available)";
            }
            
            messageContent = `Generated Plan:\n${planContent}`;
            console.log(`📡 Plan streaming - Generated formatted content for final message: ${messageContent.length} chars`);
        } else {
            // For partial streaming, we can't format incomplete plan data
            // So we'll stream a simple progress message instead
            const wordIndex = rawData.streaming?.word_index || 0;
            const totalWords = rawData.streaming?.total_words || 0;
            
            if (totalWords > 0) {
                const progress = Math.round((wordIndex / totalWords) * 100);
                messageContent = `Generating plan... (${progress}% complete)`;
            } else {
                messageContent = 'Generating plan...';
            }
            console.log(`📡 Plan streaming - Generated progress message: "${messageContent}"`);
        }
        
        console.log(`📡 Received streaming plan: final=${isStreamingFinal}, message="${messageContent.substring(0, 50)}..."`);
        
        if (isStreamingFinal) {
            // Final streaming plan message - process as normal plan
            console.log(`📡 Final streaming plan message received for query ${queryId}`);
            
            // Clear streaming state
            setStreamingMessages(prev => {
                const newMap = new Map(prev);
                newMap.delete(streamingKey);
                return newMap;
            });
            
            setStreamingMessageIds(prev => {
                const newMap = new Map(prev);
                newMap.delete(streamingKey);
                return newMap;
            });
            
            // FIXED: Return here to prevent duplicate processing
            // The streaming final message should replace the regular plan message
            console.log(`📡 Final streaming plan processed, skipping regular plan handler`);
            return;
        } else {
            // Partial streaming plan message - update or create streaming message
            const existingMessageId = streamingMessageIds.get(streamingKey);
            
            if (existingMessageId) {
                // Update existing streaming plan message
                console.log(`📡 Updating streaming plan message ${existingMessageId} with partial content`);
                const updatedMessage = {
                    id: existingMessageId,
                    content: messageContent,
                    role: 'system' as const,
                    timestamp: new Date(),
                    metadata: {
                        queryId: activeQueryId,
                        isStreaming: true,
                        streamingKey: streamingKey,
                        stepType: 'Plan Generated',
                        workflowType: rawData.workflow_type || step.workflow_type
                    }
                };
                addMessage(conversationId, updatedMessage);
            } else {
                // Create new streaming plan message
                const newMessageId = `streaming_plan_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
                console.log(`📡 Creating new streaming plan message ${newMessageId} for key ${streamingKey}`);
                
                setStreamingMessageIds(prev => {
                    const newMap = new Map(prev);
                    newMap.set(streamingKey, newMessageId);
                    return newMap;
                });
                
                const streamingMessage = {
                    id: newMessageId,
                    content: messageContent,
                    role: 'system' as const,
                    timestamp: new Date(),
                    metadata: {
                        queryId: activeQueryId,
                        isStreaming: true,
                        streamingKey: streamingKey,
                        stepType: 'Plan Generated',
                        workflowType: rawData.workflow_type || step.workflow_type
                    }
                };
                addMessage(conversationId, streamingMessage);
            }
            
            // Update streaming state
            setStreamingMessages(prev => {
                const newMap = new Map(prev);
                newMap.set(streamingKey, messageContent);
                return newMap;
            });
            
            return; // Don't process as regular plan message yet
        }
    }
    */
    // --- END DISABLED STREAMING PLANS ---

    // --- ADDED: Handle Plan --- 
    if (stepType === 'Plan' || updateType === 'plan') {
        console.log("🟣 TRACE: Entering 'plan' handler block.");
        
        // Prevent duplicate plan processing by checking if we already processed this plan
        const planProcessingKey = `plan_${activeQueryId}_${step.raw_data?.plan_details?.timestamp || Date.now()}`;
        const existingPlanId = streamingMessageIds.get(planProcessingKey);
        if (existingPlanId) {
            console.log("🟣 TRACE: Plan already processed, skipping duplicate");
            return;
        }
        const planData = step.raw_data?.plan_details;
        // <<< ADDED: Log extracted planData >>>
        console.log("Plan Handler - Extracted planData:", planData);
        console.log("Plan Handler - Type of planData:", typeof planData);
        // <<< END ADDED >>>
        let planContent = ""; // Initialize plan content string

        // IMPROVED: Check for completion status and handle appropriately
        if (planData && typeof planData === 'object') {
            // Check if plan is marked as complete
            if (planData.is_complete === true) {
                console.log("Plan Handler - Plan marked as complete, showing completion message");
                planContent = "✅ **All planned steps have been successfully executed!**\n\nThe task has been completed according to the generated plan.";
            }
            // Check if planData has valid steps to display
            else if (Array.isArray(planData.steps) && planData.steps.length > 0) {
                console.log("Plan Handler - Formatting plan steps:", planData.steps.length);
                try {
                    // Start formatting the plan using Markdown lists
                    const formattedSteps = planData.steps.map((planStep: any, stepIndex: number) => {
                        // Format Step Description
                        let stepString = `* **Step ${stepIndex + 1}:** ${planStep.description || 'No step description'}`;
                        
                        // Format Tasks within the step
                        if (planStep.tasks && Array.isArray(planStep.tasks) && planStep.tasks.length > 0) {
                            const formattedTasks = planStep.tasks.map((task: any) => {
                                // Indent tasks under the step
                                return `  * Task: ${task.description || 'No task description'} (Agent: ${task.agent || 'N/A'})`;
                            }).join('\n'); // Join tasks with newlines
                            stepString += `\n${formattedTasks}`; // Add tasks below step description
                        }
                        return stepString;
                    }).join('\n\n'); // Join steps with double newlines for separation

                    planContent = formattedSteps;
                    console.log("Plan Handler - Successfully formatted steps");
                } catch (formatError) {
                    console.error("Plan Handler - Error during plan formatting:", formatError);
                    planContent = "(Error formatting plan details)";
                }
            }
            // Handle empty steps array but valid plan data
            else if (Array.isArray(planData.steps) && planData.steps.length === 0) {
                console.log("Plan Handler - Empty steps array, checking for other plan content");
                // Check if there's any other meaningful content
                const planKeys = Object.keys(planData).filter(key => key !== 'steps' && key !== 'is_complete');
                if (planKeys.length > 0) {
                    planContent = `📋 **Plan Structure Received**\n\n\`\`\`json\n${JSON.stringify(planData, null, 2)}\n\`\`\``;
                } else {
                    planContent = "📋 **Plan initialized** - No specific steps defined yet.";
                }
            }
            // Fallback for other plan object structures
            else {
                console.warn("[Plan Handler] Plan data received but no valid steps. Showing plan structure.");
                planContent = `📋 **Plan Data Received**\n\n\`\`\`json\n${JSON.stringify(planData, null, 2)}\n\`\`\``;
            }
        } 
        // Handle string plan data
        else if (typeof planData === 'string') {
            console.warn("[Plan Handler] Plan data received as raw string.")
            planContent = `📋 **Plan Information**\n\n\`\`\`\n${planData}\n\`\`\``;
        } 
        // No valid plan data
        else {
            console.warn("[Plan Handler] No valid plan details found in payload.")
            planContent = "📋 **Plan requested** - Details will be provided shortly.";
        }
        
        // Final message to display
        const displayMessage = planData?.is_complete === true ? planContent : `Generated Plan:\n${planContent}`;
        
        console.log(`🟣 TRACE: Adding plan message via addMessage.`);
        const messageId = `plan_${Date.now()}`;
        // Mark this plan as processed to prevent duplicates
        setStreamingMessageIds(prev => {
            const newMap = new Map(prev);
            newMap.set(planProcessingKey, messageId);
            return newMap;
        });
        
        // Get agent name for plan messages too
        const planRawAgentName = step.raw_data?.agent_name || step.raw_data?.agent || 'LLM Orchestration Planner';
        const planFriendlyAgentName = getUserFriendlyAgentName(planRawAgentName);
        
        addMessage(conversationId, {
            id: messageId,
            content: displayMessage, // Use the new formatted message
            role: 'system', // Display plan as system message
            timestamp: new Date(),
            metadata: { 
                queryId: activeQueryId, 
                isAgentProgress: true, 
                stepType: planData?.is_complete === true ? 'Plan Completed' : 'Plan Generated',
                agentName: planFriendlyAgentName,
                rawAgentName: planRawAgentName,
                planComplete: planData?.is_complete === true
            }
        });
        saveMessageToDatabase(conversationId, uuidv4(), displayMessage, 'system', { 
            isAgentProgress: true, 
            stepType: planData?.is_complete === true ? 'Plan Completed' : 'Plan Generated', 
            agentName: planFriendlyAgentName,
            rawAgentName: planRawAgentName,
            queryId: activeQueryId,
            planComplete: planData?.is_complete === true
        });

        // Optionally update agent status with extracted agent name and workflow type
        const planAgentName = friendlyExtractedAgentName || planFriendlyAgentName || 'Planner';
        console.log(`[useRealTimeUpdates] Plan generated by ${planAgentName} (Workflow: ${extractedWorkflowType})`);
        setAgentStatus("Plan generated", 'plan', planAgentName);

        return; // Handled this update type
    }
    // --- END ADDED ---

    // The rest of the hook handles other step types (status, result, progress etc.)
    else {
        // --- ADDED: Debugging log --- 
        console.log("🟣 TRACE: Entering FINAL else block for adding message.");
        // --- Content construction logic (remains largely the same) --- 
      // DEBUG: Always log step type for troubleshooting
      console.log(`🚨 Step Processing Debug - currentStepType="${currentStepType}", step.type="${step.type}", step.message="${step.message?.substring(0, 50)}..."`);
      
      // Get agent names early for use throughout processing
      const rawAgentName = rawData.agent_name || rawData.agent || step.raw_data?.agent_name || step.raw_data?.agent;
      const friendlyAgentName = rawAgentName ? getUserFriendlyAgentName(rawAgentName) : null;
      
      // PRIORITY CHECK: Handle tool calling first, regardless of step.message content
      if (currentStepType === 'Calling Tool') {
        // Handle tool calling - SEPARATE the LLM text from the tool call
        console.log(`🔧 Tool Call Debug - currentStepType="${currentStepType}"`);
        console.log(`🔧 Tool Call Debug - Full rawData:`, rawData);
        console.log(`🔧 Tool Call Debug - Full step:`, step);
        
        // Agent names already declared at top level
        
        // Try multiple sources for tool name - CHECK tool_args from MCP params
        let toolName = rawData.tool_name || step.tool_name || step.raw_data?.tool_name;
        
        // NEW: Check tool_args which might contain the actual tool name
        if (!toolName && rawData.tool_args) {
          try {
            const parsedArgs = typeof rawData.tool_args === 'string' ? JSON.parse(rawData.tool_args) : rawData.tool_args;
            if (parsedArgs && parsedArgs.name) {
              toolName = parsedArgs.name;
              console.log(`🔧 Tool Call Debug: extracted toolName from tool_args: "${toolName}"`);
            }
          } catch (e) {
            console.log(`🔧 Tool Call Debug: failed to parse tool_args:`, e);
          }
        }
        
        // If still no tool name, try to extract from step.message
        if (!toolName && step.message) {
          const match = step.message.match(/\[Calling tool (\S+)/);
          if (match) {
            toolName = match[1];
          }
        }
        
        toolName = toolName || 'Unknown Tool';
        console.log(`🔧 Tool Call Debug: final toolName="${toolName}"`);
        
        // STEP 1: Extract and separate LLM text from tool call
        const fullMessage = step.message || '';
        
        // SIMPLIFIED: Check if the entire message is just a tool call
        const isOnlyToolCall = /^\s*\[Calling tool [^\]]+\]\s*$/.test(fullMessage);
        
        console.log(`🔧 Tool Call Debug: isOnlyToolCall=${isOnlyToolCall}, fullMessage="${fullMessage}"`);
        
        let llmTextPart = '';
        let hasLLMText = false;
        let toolCallText = '';
        
        if (isOnlyToolCall) {
          // The entire message is just a tool call - no LLM text
          toolCallText = fullMessage.trim();
          llmTextPart = '';
          hasLLMText = false;
          console.log(`🔧 Tool Call Debug: Detected pure tool call: "${toolCallText}"`);
        } else {
          // IMPROVED: Use manual brace counting for robust tool call extraction
          // This handles deeply nested JSON like chart configurations
          
          let toolCallMatch = null;
          
          // First, look for the start of a tool call
          const toolCallStartMatch = fullMessage.match(/\[Calling tool [^\s\]]+/);
          if (toolCallStartMatch) {
            const toolCallStart = toolCallStartMatch.index!;
            let braceCount = 0;
            let inArgs = false;
            let toolCallEnd = -1;
            
            // Scan from the tool call start to find the complete tool call
            for (let i = toolCallStart; i < fullMessage.length; i++) {
              const char = fullMessage[i];
              
              if (char === '{' && !inArgs) {
                // Found start of args - start counting braces
                inArgs = true;
                braceCount = 1;
              } else if (char === '{' && inArgs) {
                braceCount++;
              } else if (char === '}' && inArgs) {
                braceCount--;
                if (braceCount === 0) {
                  // Found end of args - look for closing ]
                  for (let j = i + 1; j < fullMessage.length; j++) {
                    if (fullMessage[j] === ']') {
                      toolCallEnd = j;
                      break;
                    } else if (!/\s/.test(fullMessage[j])) {
                      // Non-whitespace character before ], this isn't the end
                      break;
                    }
                  }
                  break;
                }
              } else if (char === ']' && !inArgs) {
                // Simple tool call without args
                toolCallEnd = i;
                break;
              }
            }
            
            if (toolCallEnd > toolCallStart) {
              toolCallText = fullMessage.substring(toolCallStart, toolCallEnd + 1);
              toolCallMatch = [toolCallText]; // Create match array for compatibility
              console.log(`🔧 Tool Call Debug: Extracted tool call with brace counting: "${toolCallText.substring(0, 100)}..."`);
            }
          }
          
          // Fallback: Try simple regex patterns if brace counting failed
          if (!toolCallMatch) {
            const fallbackPatterns = [
              /\[Calling tool [^\]]+\]$/,
              /\[Calling tool [^\]]+\]$/m,
              /\[Calling tool.*?\]$/s
            ];
            
            for (const pattern of fallbackPatterns) {
              toolCallMatch = fullMessage.match(pattern);
              if (toolCallMatch) {
                toolCallText = toolCallMatch[0];
                console.log(`🔧 Tool Call Debug: Matched fallback pattern: "${toolCallText.substring(0, 100)}..."`);
                break;
              }
            }
          }
          
          if (toolCallMatch) {
            // There's a tool call at the end - extract the text before it
            const toolCallStart = fullMessage.lastIndexOf(toolCallText);
            llmTextPart = fullMessage.substring(0, toolCallStart).trim();
            hasLLMText = llmTextPart.length > 0;
          } else {
            // No tool call pattern found, treat entire message as LLM text
            llmTextPart = fullMessage.trim();
            hasLLMText = llmTextPart.length > 0;
            toolCallText = '';
          }
        }
        
        console.log(`🔧 Tool Call Separation - hasLLMText: ${hasLLMText}, llmTextPart: "${llmTextPart.substring(0, 50)}...", toolCallText: "${toolCallText.substring(0, 50)}..."`);
        
        // STEP 2: Add LLM text as separate system message (if it exists)
        if (hasLLMText) {
          const llmMessage = {
            id: `${messageId}_llm_text`, 
            content: llmTextPart, 
            role: 'system' as const, // Changed to system to maintain agent styling
            timestamp: new Date(),
            metadata: { 
              isAgentProgress: true, // Changed to true for system styling
              stepType: 'Agent Response', // Add step type for proper styling
              agent: rawData.agent,
              agentName: friendlyAgentName,
              rawAgentName: rawAgentName,
              queryId: activeQueryId 
            }
          };
          
          addMessage(conversationId, llmMessage);
          
          try {
            saveMessageToDatabase(conversationId, llmMessage.id, llmTextPart, 'system', {
              isAgentProgress: true,
              stepType: 'Agent Response',
              agentName: friendlyAgentName,
              rawAgentName: rawAgentName,
              queryId: activeQueryId
            });
          } catch (error) {
            console.error('Error saving LLM text message:', error);
          }
        }
        
        // STEP 3: Create user-friendly tool call message
        let userFriendlyMessage = '';
        
        // Create simple, clean user-friendly messages based on tool name
        // All details are now in the toggle, so we just need clean action names
        const toolNameMappings: { [key: string]: string } = {
          // Web search tools
          'websearch_websearch-search': 'Searching web',
          'websearch-search': 'Searching web',
          
          // Fetch tools
          'fetch_fetch': 'Reading website',
          'fetch': 'Reading website',
          
          // Markdown editor tools
          'markdown-editor_create_document': 'Creating document',
          'create_document': 'Creating document',
          'markdown-editor_edit_document': 'Editing document',
          'edit_document': 'Editing document',
          'markdown-editor_append_content': 'Adding content to document',
          'append_content': 'Adding content to document',
          'markdown-editor_add_image': 'Adding image to document',
          'add_image': 'Adding image to document',
          'markdown-editor_convert_to_md': 'Converting to markdown',
          'convert_to_md': 'Converting to markdown',
          'markdown-editor_convert_from_md': 'Converting from markdown',
          'convert_from_md': 'Converting from markdown',
          'markdown-editor_preview': 'Generating preview',
          'preview': 'Generating preview',
          'markdown-editor_live_preview': 'Starting live preview',
          'live_preview': 'Starting live preview',
          'markdown-editor_add_chart': 'Adding chart to document',
          'add_chart': 'Adding chart to document',
          'markdown-editor_extract_table': 'Extracting table data',
          'extract_table': 'Extracting table data',
          'markdown-editor_create_chart': 'Creating chart',
          'create_chart': 'Creating chart',
          'markdown-editor_create_chart_from_data': 'Creating chart',
          'create_chart_from_data': 'Creating chart',
          'markdown-editor_get_chart_template': 'Getting chart template',
          'get_chart_template': 'Getting chart template',
          'markdown-editor_create_document_with_chart': 'Creating document with chart',
          'create_document_with_chart': 'Creating document with chart',
          'markdown-editor_get_filesystem_path': 'Getting filesystem path',
          'get_filesystem_path': 'Getting filesystem path',
          
          // Memory/storage tools
          'qdrant-store': 'Storing in memory',
          'qdrant_store': 'Storing in memory',
          'store': 'Storing in memory',
          'qdrant-find': 'Searching memory',
          'qdrant_find': 'Searching memory',
          'find': 'Searching memory',
          
          // File system tools
          'read_file': 'Reading file',
          'filesystem_read_file': 'Reading file',
          'read_multiple_files': 'Reading files',
          'filesystem_read_multiple_files': 'Reading files',
          'write_file': 'Writing file',
          'filesystem_write_file': 'Writing file',
          'edit_file': 'Editing file',
          'filesystem_edit_file': 'Editing file',  
          'create_directory': 'Creating directory',
          'filesystem_create_directory': 'Creating directory',
          'list_directory': 'Listing directory',
          'filesystem_list_directory': 'Listing directory',
          'directory_tree': 'Getting directory tree',
          'filesystem_directory_tree': 'Getting directory tree',
          'move_file': 'Moving file',
          'filesystem_move_file': 'Moving file',
          'search_files': 'Searching files',
          'filesystem_search_files': 'Searching files',
          'get_file_info': 'Getting file info',
          'filesystem_get_file_info': 'Getting file info',
          'list_allowed_directories': 'Listing allowed directories',
          'filesystem_list_allowed_directories': 'Listing allowed directories',
        };
        
        // Use mapping or create a clean default
        if (toolNameMappings[toolName]) {
          userFriendlyMessage = toolNameMappings[toolName];
        } else {
          // Clean up tool name for display - remove prefixes and make readable
          // FIXED: Add safety check for toolName
          if (toolName && typeof toolName === 'string') {
            let cleanToolName = toolName
              .replace(/^(markdown-editor_|filesystem_|qdrant[-_]|websearch[-_])/, '') // Remove common prefixes
              .replace(/[-_]/g, ' ') // Replace dashes/underscores with spaces
              .toLowerCase()
              .replace(/\b\w/g, (l: string) => l.toUpperCase()); // Capitalize words
            
            userFriendlyMessage = `${cleanToolName}`;
          } else {
            userFriendlyMessage = `Tool`;
          }
        }
        
        // STEP 4: Add the tool call message with special styling metadata and tool arguments
        const toolArguments = rawData.tool_arguments || rawData.tool_args;
        
        // FIXED: Use a more consistent ID generation for tool calls
        // Use timestamp and tool name to create a unique but predictable ID
        const timestamp = Date.now();
        const safeToolName = (toolName && typeof toolName === 'string') ? toolName.replace(/[^a-zA-Z0-9]/g, '_') : 'unknown_tool';
        const toolCallId = `tool_call_${timestamp}_${safeToolName}`;
        
        const toolCallMessage = {
          id: toolCallId, 
          content: userFriendlyMessage.trim(), 
          role: 'system' as const, 
          timestamp: new Date(),
          metadata: { 
            isAgentProgress: true, 
            stepType: 'Calling Tool', // Explicit step type for styling
            isToolCall: true, // Special flag for tool calling
            agent: rawData.agent,
            agentName: friendlyAgentName,
            rawAgentName: rawAgentName,
            serverName: step.server_name, 
            toolName: toolName, // Use our extracted tool name
            toolArguments: toolArguments, // Store tool arguments for toggle display (check both field names)
            queryId: activeQueryId,
            toolCallTimestamp: timestamp // Store timestamp for result association
          }
        };
        
        // Add the special tool call message
        addMessage(conversationId, toolCallMessage);
        
        // Save to database with special tool call metadata
        try {
          saveMessageToDatabase(conversationId, toolCallMessage.id, userFriendlyMessage.trim(), 'system', {
            isAgentProgress: true,
            stepType: 'Calling Tool',
            isToolCall: true,
            agentName: friendlyAgentName,
            rawAgentName: rawAgentName,
            toolName: toolName,
            toolArguments: rawData.tool_arguments || rawData.tool_args, // Check both field names
            queryId: activeQueryId
          });
        } catch (error) {
          console.error('Error saving tool call message:', error);
        }
        
        // Return early to prevent normal message processing
        return;
      } 
      
      // PRIORITY CHECK: Handle Tool Result - associate with corresponding tool call
      if (currentStepType === 'Tool Result') {
        console.log(`🔧 Tool Result Debug - Received tool result for tool: ${step.tool_name || rawData.tool_name}`);
        
        // FIXED: Find the most recent tool call with the same tool name and query ID
        // This approach is more reliable than trying to generate matching IDs
        const toolName = step.tool_name || rawData.tool_name;
        
        // We'll store the tool result with a reference to find the matching tool call
        // The UI will handle the association by looking for the most recent tool call with matching tool name
        const toolResult = rawData.tool_result_summary || rawData.tool_result || rawData.tool_call_result || step.message || 'Tool completed';
        console.log(`🔧 Tool Result Debug - Extracted result:`, toolResult);
        console.log(`🔧 Tool Result Debug - Tool name for association: ${toolName}`);
        console.log(`🔧 Tool Result Debug - Query ID: ${activeQueryId}`);
        console.log(`🔧 Tool Result Debug - Full raw data:`, rawData);
        
        // Instead of creating a new message, we'll store the result data for the UI to associate
        // The UI will handle displaying this as part of the tool call toggle
        console.log(`🔧 Tool Result - Storing result for tool: ${toolName}`);
        
        // Create a tool result message that the UI can use to associate with the tool call
        const safeToolNameForResult = (toolName && typeof toolName === 'string') ? toolName.replace(/[^a-zA-Z0-9]/g, '_') : 'unknown_tool';
        const resultTimestamp = Date.now();
        const toolResultMessage = {
          id: `tool_result_${resultTimestamp}_${safeToolNameForResult}`,
          content: '', // Empty content - this will be handled by the toggle UI
          role: 'system' as const,
          timestamp: new Date(),
          metadata: {
            isAgentProgress: true,
            stepType: 'Tool Result',
            isToolResult: true,
            toolName: toolName,
            toolResult: toolResult,
            queryId: activeQueryId,
            agentName: friendlyAgentName,
            rawAgentName: rawAgentName,
            // Store additional info for association
            resultTimestamp: resultTimestamp
          }
        };
        
        console.log(`🔧 Tool Result Debug - Created message with metadata:`, {
          id: toolResultMessage.id,
          toolName: toolResultMessage.metadata.toolName,
          queryId: toolResultMessage.metadata.queryId,
          resultTimestamp: toolResultMessage.metadata.resultTimestamp,
          hasToolResult: !!toolResultMessage.metadata.toolResult
        });
        
        addMessage(conversationId, toolResultMessage);
        
        try {
          saveMessageToDatabase(conversationId, toolResultMessage.id, '', 'system', {
            isAgentProgress: true,
            stepType: 'Tool Result',
            isToolResult: true,
            toolName: toolName,
            toolResult: toolResult,
            queryId: activeQueryId,
            agentName: friendlyAgentName,
            rawAgentName: rawAgentName
          });
        } catch (error) {
          console.error('Error saving tool result message:', error);
        }
        
        return; // Don't process as regular message
      }
      
      // Handle other step types (not Calling Tool or Tool Result)
      if (step.message && step.message.trim() !== '' && !step.message.startsWith('send_request: response=')) {
        content = step.message.trim();
      } 
      // ... (fallback logic: llm_text_output, default)
      else if (rawData.llm_text_output) {
        content = rawData.llm_text_output.trim();
      } else {
          const serverInfo = rawData.server_name ? ` (Server: ${rawData.server_name})` : '';
          content = `${currentStepType}${serverInfo}`.trim(); 
      }
      // --- END Content construction --- 
        
      // --- ADDED: Debugging log --- 
      console.log(`🟣 TRACE: Adding general message via addMessage in else block: Content='${content.substring(0,50)}...'`);
      console.log("--- Processing Step Data (Adding to Chat History) ---");
      console.log("latestStepData:", JSON.stringify(latestStepData, null, 2));
      console.log(`Constructed Content: ${content}`);

      // Agent names already declared at top level - no need to redeclare

      const progressMessage = {
        id: messageId, content, role: 'system' as const, timestamp: new Date(),
        metadata: { 
          isAgentProgress: true, 
          stepType: currentStepType, 
          agent: rawData.agent, // Keep original for backward compatibility
          agentName: friendlyExtractedAgentName || friendlyAgentName, // Use extracted name first
          rawAgentName: extractedAgentName || rawAgentName, // Use extracted name first
          serverName: step.server_name, 
          toolName: step.tool_name, 
          queryId: activeQueryId,
          workflowType: extractedWorkflowType // Add workflow type to metadata
        }
      };
      addMessage(conversationId, progressMessage);
      try { 
          // The 'return' statements earlier prevent this line from being reached for 'status' and 'Chatting' types.
          // Generate a unique ID for this system message
          const systemMessageId = uuidv4(); 
          saveMessageToDatabase(conversationId, systemMessageId, content, 'system', { 
            isAgentProgress: true, 
            stepType: currentStepType || 'Unknown', 
            agentName: friendlyAgentName,
            rawAgentName: rawAgentName,
            queryId: activeQueryId 
          }); 
      } catch (error) { console.error(error); }
    }
    
  // Dependencies updated
  }, [latestStepData, activeQueryId, addMessage, saveMessageToDatabase, setAgentStatus, setWorkflowType, cleanupQueryResources]);

  // Handle human input submissions from user
  const submitHumanInput = useCallback(async (input: string) => {
    // --- MODIFIED: Guard against null viewedConversationId --- 
    const currentViewedConvId = viewedConversationId;
    if (!currentViewedConvId) {
      console.error("Cannot submit human input: No conversation is currently viewed.");
      return null; // Or throw error
    }
    const request = perConversationState[currentViewedConvId]?.humanInputRequest;
    if (!request) {
      console.warn("Cannot submit human input: No active request found for the current conversation.");
      return null;
    }
    const queryIdForInput = request.queryId;
    // --- ADDED: Get inputId from request --- 
    const inputIdForInput = request.inputId;
    // --- END ADDED ---

    setGlobalProcessingState(true);
    
    try {
      const apiAny = api as any;
      // --- REMOVED Simulation Logic --- 
      /*
      if (!apiAny.submitHumanInput) {
        console.warn("submitHumanInput API function not available, simulating success.");
        addMessage(currentViewedConvId, { id: `human_input_${Date.now()}`, content: `Input: ${input}`, role: 'system', timestamp: new Date() });
        // Clear the request for the specific conversation
        setPerConversationState(prev => ({
          ...prev,
          [currentViewedConvId]: {
            ...(prev[currentViewedConvId] || { isLoading: false, humanInputRequest: null, decisionState: initialDecisionState }),
            humanInputRequest: null
          }
        }));
        return { success: true }; 
      }
      */
      // --- END REMOVED --- 

      console.log(`Submitting human input ${inputIdForInput} for query ${queryIdForInput}, tool ${request.toolName}`);
      // Now directly call the function which should exist on the api object
      const response = await (api as any).submitHumanInput(inputIdForInput, queryIdForInput, request.toolName, input);
      
      // Clear the request for the specific conversation *after* successful API call
      setPerConversationState(prev => ({
        ...prev,
        [currentViewedConvId]: {
          ...(prev[currentViewedConvId] || { isLoading: false, humanInputRequest: null, isWaitingForClarification: false }),
          humanInputRequest: null
        }
      }));
      console.log("Human input submitted successfully, request cleared.");
      return response.data;
    } catch (error) {
      console.error(`Error submitting human input for query ${queryIdForInput}:`, error);
      if (queryIdForInput) {
          cleanupQueryResources(queryIdForInput); // Cleanup on error
      }
      return null;
    }
  }, [viewedConversationId, perConversationState, api, addMessage, cleanupQueryResources]);

  // Handle human input cancellation
  const cancelHumanInput = useCallback(() => {
    // --- MODIFIED: Guard against null viewedConversationId --- 
    const currentViewedConvId = viewedConversationId;
    if (!currentViewedConvId) {
      console.error("Cannot cancel human input: No conversation is currently viewed.");
      return;
    }
    const request = perConversationState[currentViewedConvId]?.humanInputRequest;
     if (!request) {
      console.warn("Cannot cancel human input: No active request found for the current conversation.");
      return;
    }
    const queryIdToCancel = request.queryId;
    // --- END MODIFIED --- 

    try {
      const apiAny = api as any;
      const toolNameToCancel = request.toolName;
      
      // Clear the request optimistically for the specific conversation
      setPerConversationState(prev => ({
        ...prev,
        [currentViewedConvId]: {
          ...(prev[currentViewedConvId] || { isLoading: false, humanInputRequest: null, isWaitingForClarification: false }),
          humanInputRequest: null
        }
      }));
      console.log("Human input request cleared optimistically.");

      if (!apiAny.submitHumanInput) {
        console.warn("submitHumanInput API function not available for cancellation.");
        // Don't cleanup here, let finally handle it
        return;
      }

      console.log(`Submitting CANCELLED human input for query ${queryIdToCancel}, tool ${toolNameToCancel}`);
      // Submit cancellation to backend (fire and forget)
      apiAny.submitHumanInput(queryIdToCancel, toolNameToCancel, "CANCELLED")
        .catch((err: Error) => console.warn("Error submitting cancellation to backend:", err));

    } catch (error) { 
      console.error("Error during human input cancellation logic:", error); 
    }
    finally { 
      // Always cleanup resources associated with the query when cancelled
      if (queryIdToCancel) {
          console.log(`Performing cleanup for cancelled query: ${queryIdToCancel}`);
          cleanupQueryResources(queryIdToCancel); 
      }
    }
  }, [viewedConversationId, perConversationState, api, cleanupQueryResources]);

  // --- MODIFIED: Return state scoped to viewedConversationId ---
  const currentScopedState = viewedConversationId ? perConversationState[viewedConversationId] : null;
  return {
    activeQueryId, // Still useful to know the globally active query
    isConnected: wsConnected,
    status: wsStatus,
    latestStepData,
    isAnyQueryProcessing: currentScopedState?.isLoading ?? false, // Use scoped loading state
    humanInputRequest: currentScopedState?.humanInputRequest ?? null, // Use scoped request
    submitHumanInput,
    cancelHumanInput,
    handleCoordinatorResponse,
    connectToWebSocket,
    hasActiveWebSocketForQuery,
    cleanupQueryResources,
    isWaitingForClarification: currentScopedState?.isWaitingForClarification ?? false,
  };
  // --- END MODIFIED ---
};

export default useRealTimeUpdates;