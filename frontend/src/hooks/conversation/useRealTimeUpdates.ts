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

        // --- MODIFIED: Extract final text block after the LAST tool call placeholder --- 
        let formattedContent = rawResultText.trim(); // Default to full trimmed text
        const toolCallMarker = '[Calling tool';
        const lastToolCallIndex = rawResultText.lastIndexOf(toolCallMarker);

        if (lastToolCallIndex !== -1) {
          // Find the end of that specific placeholder line (look for the next ']')
          const endBracketIndex = rawResultText.indexOf(']', lastToolCallIndex);
          if (endBracketIndex !== -1) {
            // Extract everything AFTER the closing bracket of the last tool call
            const subsequentText = rawResultText.substring(endBracketIndex + 1).trim();
            if (subsequentText) { // Only use extracted part if it's not empty
              formattedContent = subsequentText;
              console.log(`[Result Parse] Extracted final answer after last tool call marker.`)
            } else {
              // This case might happen if the result ends exactly with the placeholder
              console.log(`[Result Parse] Found last tool marker but no non-empty content after it, using full result.`);
              // Keep the default formattedContent (full text)
            }
          } else {
            // Malformed placeholder? Fallback to full text
            console.log(`[Result Parse] Found last tool marker but no closing ']', using full result.`);
          }
        } else {
          // No tool calls found in the result string
          console.log(`[Result Parse] No tool call markers found, using full result.`);
        }
        // --- END MODIFIED Extraction --- 
        
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
        await saveMessageToDatabase(targetConversationId, formattedContent, 'assistant', metadata); // Use targetConversationId
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
        saveMessageToDatabase(conversationId, clarificationMessage, 'assistant', { queryId: activeQueryId, isClarificationRequest: true });

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
        if (step.step_type === 'file_processed' || step.step_type === 'file_error') {
          // --- DEBUGGING ADDED ---
          console.log("[useRealTimeUpdates] Received file status update (after query finished?):", step);
          // --- END DEBUGGING ---
          const fileId = step.raw_data?.file_id;
          const status = step.step_type === 'file_processed' ? 'completed' as const : 'error' as const;
          const errorMsg = step.step_type === 'file_error' ? step.message : undefined;
          const messageId = step.raw_data?.messageId; // Use the messageId from payload
          if (fileId) {
            console.log(`Received file status update: ${fileId} -> ${status}`);
            // Find the message where the file was originally attached
            // --- MODIFIED: Use messageId directly --- 
            const targetConversationId = conversationId; // Get from processingQueriesRef
            const targetMessageId = messageId; 
            console.log(`Attempting to update file status for: convId=${targetConversationId}, msgId=${targetMessageId}, fileId=${fileId}`);
            if (targetMessageId) {
              // --- DEBUGGING ADDED ---
              console.log("[useRealTimeUpdates] Calling updateFileAttachmentStatus...", { targetConversationId, targetMessageId, fileId, status, errorMsg });
              // --- END DEBUGGING ---
              updateFileAttachmentStatus(targetConversationId, targetMessageId, fileId, status, errorMsg);
              console.log(`[useRealTimeUpdates] Called updateFileAttachmentStatus for file ${fileId} in message ${targetMessageId}`);
            } else {
              console.warn(`[useRealTimeUpdates] Missing messageId in file status update payload for file ${fileId}. Cannot update status.`);
            }
            // --- END MODIFICATION ---
          }
          return; // Don't add a new message for file status updates
        }
        console.warn(`Query ${activeQueryId} no longer processing, skipping progress message.`);
        return; // Query was cleaned up
    }
    
    // --- MODIFIED: Handle 'result' step - check for duplicates and call processFinalResponse directly --- 
    if (stepType === 'result') {
        const queryId = step.queryId;
        if (queryId && processedQueryIdsRef.current.has(queryId)) {
            // If already processed, just log and ignore this duplicate step
            console.warn(`[useEffect] Received duplicate 'result' step for already processed query ${queryId}. Ignoring.`);
        } else {
            // If it's a new 'result' step, log and call processFinalResponse directly.
            // processFinalResponse now handles adding message, marking processed, and cleanup.
            console.log(`[useEffect] Received step_type 'result' for new query ${queryId}. Calling processFinalResponse.`);
            processFinalResponse(step.raw_data, conversationId, queryId)
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
          saveMessageToDatabase(conversationId, clarificationMessage, 'assistant', { queryId: activeQueryId, isClarificationRequest: true, explanation: explanation });

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
        const agentName = step.raw_data?.agent_name || step.raw_data?.selected_agent || 'Router'; // Also check selected_agent
        const routingMsg = `Routing to ${agentName}`; // Changed message format
        console.log(`[useRealTimeUpdates] Routing step_type 'routing' to AgentStatusIndicator: ${routingMsg} (Agent: ${agentName})`);
        setAgentStatus(routingMsg, 'routing', agentName); // Use lowercase 'routing' for consistency
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
        const agentName = rawData?.agent || 'Agent'; // Try to get agent name
        const runningMsg = `${agentName} is running...`; 
        console.log(`[useRealTimeUpdates] Routing step_type 'running' to AgentStatusIndicator: ${runningMsg}`); 
        setAgentStatus(runningMsg, 'running', agentName); // Use 'running' status type
        return; // Prevent adding to history
    }
    // --- END ADDED ---
    
    if (stepType?.toLowerCase() === 'chatting') {
        // --- MODIFIED: Log raw_data and extracted name --- 
        console.log("[useRealTimeUpdates] Raw data for Chatting step:", step.raw_data);
        const agentName = step.raw_data?.agent || 'Agent'; // Use 'agent' instead of 'agent_name'
        console.log(`[useRealTimeUpdates] Extracted agentName for Chatting: ${agentName}`);
        const runningMsg = `${agentName} is running...`; 
        console.log(`[useRealTimeUpdates] Routing step_type 'Chatting' to AgentStatusIndicator: ${runningMsg}`); 
        setAgentStatus(runningMsg, 'Chatting', agentName); 
        console.log("[useRealTimeUpdates] Explicit RETURN after handling Chatting."); // Added log
        return; 
    }
    
    // Skip other meta step types that shouldn't show status or be added to history
    if (stepType === 'Finished') {
        setAgentStatus(null, null); 
        setWorkflowType(null); // Clear workflow type here
        return; 
    }
    
    // --- ADDED: Handle file status updates ---
    if (step.step_type === 'file_processed' || step.step_type === 'file_error') {
      // --- DEBUGGING ADDED ---
      console.log("[useRealTimeUpdates] Received file status update:", step);
      // --- END DEBUGGING ---
      const fileId = step.raw_data?.file_id;
      const status = step.step_type === 'file_processed' ? 'completed' as const : 'error' as const;
      const errorMsg = step.step_type === 'file_error' ? step.message : undefined;
      const messageId = step.raw_data?.messageId; // Use messageId from payload
      if (fileId && conversationId) {
        console.log(`Received file status update: ${fileId} -> ${status} for conversation ${conversationId}`);
        // Find the message containing this file attachment
        // --- MODIFIED: Use messageId directly --- 
        const targetMessageId = messageId;
        console.log(`Attempting to update file status for: convId=${conversationId}, msgId=${targetMessageId}, fileId=${fileId}`);
        if (targetMessageId) {
          // --- DEBUGGING ADDED ---
          console.log("[useRealTimeUpdates] Calling updateFileAttachmentStatus...", { conversationId, targetMessageId, fileId, status, errorMsg });
          // --- END DEBUGGING ---
          updateFileAttachmentStatus(conversationId, targetMessageId, fileId, status, errorMsg);
          console.log(`[useRealTimeUpdates] Called updateFileAttachmentStatus for file ${fileId} in message ${targetMessageId}`);
        } else {
          console.warn(`[useRealTimeUpdates] Missing messageId in file status update payload for file ${fileId}. Cannot update status.`);
        }
        // --- END MODIFICATION ---
      }
      // It might be useful to show a small system message confirming success/error?
      // For now, just update the status and don't add a new message.
      return; // Don't proceed to add a new message for file status updates
    }
    // --- END ADDED --- 

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

    // --- ADDED: Handle Plan --- 
    if (stepType === 'Plan') {
        console.log("🟣 TRACE: Entering 'plan' handler block.");
        const planData = step.raw_data?.plan_details;
        // <<< ADDED: Log extracted planData >>>
        console.log("Plan Handler - Extracted planData:", planData);
        console.log("Plan Handler - Type of planData:", typeof planData);
        // <<< END ADDED >>>
        let planContent = ""; // Initialize plan content string

        // Check if planData exists and has steps
        // <<< ADDED: Log check result >>>
        const planCheck = planData && Array.isArray(planData.steps) && planData.steps.length > 0;
        console.log("Plan Handler - Steps check (planData && Array.isArray(planData.steps) && planData.steps.length > 0):", planCheck);
        // <<< END ADDED >>>
        if (planCheck) {
            try { // <<< ADDED: Try/catch around formatting >>>
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
                // <<< ADDED: Log formatted content >>>
                console.log("Plan Handler - Successfully formatted steps:", planContent);
                // <<< END ADDED >>>
            } catch (formatError) {
                console.error("Plan Handler - Error during plan formatting:", formatError);
                planContent = "(Error formatting plan details)";
            } // <<< END ADDED >>>
        } 
        // Fallback if planData is not structured as expected
        else if (typeof planData === 'object' && planData !== null) {
            console.warn("[Plan Handler] Plan data received but steps array missing or empty. Displaying JSON.")
            planContent = `\`\`\`json\n${JSON.stringify(planData, null, 2)}\n\`\`\``;
        } else if (typeof planData === 'string') {
            console.warn("[Plan Handler] Plan data received as raw string.")
            planContent = `\`\`\`\n${planData}\n\`\`\``;
        } else {
            console.warn("[Plan Handler] No valid plan details found in payload.")
            planContent = "(Plan details not available)"
        }
        
        // Final message to display
        const displayMessage = `Generated Plan:\n${planContent}`;
        
        console.log(`🟣 TRACE: Adding plan message via addMessage.`);
        const messageId = `plan_${Date.now()}`;
        addMessage(conversationId, {
            id: messageId,
            content: displayMessage, // Use the new formatted message
            role: 'system', // Display plan as system message
            timestamp: new Date(),
            metadata: { queryId: activeQueryId, isAgentProgress: true, stepType: 'Plan Generated' } // Keep metadata
        });
        saveMessageToDatabase(conversationId, displayMessage, 'system', { isAgentProgress: true, stepType: 'Plan Generated', queryId: activeQueryId });

        // Optionally update agent status
        setAgentStatus("Plan generated", 'plan', 'Planner');

        return; // Handled this update type
    }
    // --- END ADDED --- 

    // The rest of the hook handles other step types (status, result, progress etc.)
    else {
        // --- ADDED: Debugging log --- 
        console.log("🟣 TRACE: Entering FINAL else block for adding message.");
        // --- Content construction logic (remains largely the same) --- 
      const agentPrefix = rawData.agent_name ? `[${rawData.agent_name}] ` : '';
      if (step.message && step.message.trim() !== '' && !step.message.startsWith('send_request: response=')) {
        content = `${agentPrefix}${step.message}`.trim();
      } 
      // ... (fallback logic: llm_text_output, Calling Tool, Tool Result, default)
      else if (rawData.llm_text_output) {
        content = `${agentPrefix}${rawData.llm_text_output}`.trim();
      } else if (currentStepType === 'Calling Tool') {
          //... existing tool call formatting
        const toolName = rawData.tool_name || 'Unknown Tool';
        let argsString = '';
        if (rawData.tool_arguments) {
          try {
            const args = typeof rawData.tool_arguments === 'string' ? JSON.parse(rawData.tool_arguments) : rawData.tool_arguments;
            argsString = Object.entries(args).map(([key, value]) => `${key}=${JSON.stringify(value)}`).join(', ');
              argsString = argsString.substring(0, 150) + (argsString.length > 150 ? '...' : '');
          } catch (e) {
            argsString = String(rawData.tool_arguments).substring(0, 150) + (String(rawData.tool_arguments).length > 150 ? '...' : '');
          }
        }
        content = `${agentPrefix}Calling Tool: ${toolName}(${argsString})`.trim();
      } else if (currentStepType === 'Tool Result' && rawData.tool_result_summary) { 
         content = `${agentPrefix}Tool Result: ${rawData.tool_result_summary}`.trim();
      } else {
          const serverInfo = rawData.server_name ? ` (Server: ${rawData.server_name})` : '';
          content = `${agentPrefix}${currentStepType}${serverInfo}`.trim(); 
      }
      // --- END Content construction --- 
        
      // --- ADDED: Debugging log --- 
      console.log(`🟣 TRACE: Adding general message via addMessage in else block: Content='${content.substring(0,50)}...'`);
      console.log("--- Processing Step Data (Adding to Chat History) ---");
      console.log("latestStepData:", JSON.stringify(latestStepData, null, 2));
      console.log(`Constructed Content: ${content}`);

      const progressMessage = {
        id: messageId, content, role: 'system' as const, timestamp: new Date(),
        metadata: { 
          isAgentProgress: true, 
          stepType: currentStepType, 
          agent: step.agent, // Use correct key from WebSocket payload
          serverName: step.server_name, 
          toolName: step.tool_name, 
          queryId: activeQueryId 
        }
      };
      addMessage(conversationId, progressMessage);
      try { 
          // The 'return' statements earlier prevent this line from being reached for 'status' and 'Chatting' types.
          saveMessageToDatabase(conversationId, content, 'system', { isAgentProgress: true, stepType: currentStepType || 'Unknown', queryId: activeQueryId }); 
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
      const response = await api.submitHumanInput(inputIdForInput, queryIdForInput, request.toolName, input);
      
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