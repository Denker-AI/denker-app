import { useEffect, useState, useCallback, useRef } from 'react';

// Define the types of steps that match MCP Agent's ProgressAction enum values
export type AgentStepType = 
  'Starting' | 
  'Loaded' | 
  'Running' | 
  'Initialized' | 
  'Chatting' | 
  'Routing' | 
  'Planning' | 
  'Ready' | 
  'Calling Tool' | 
  'Finished' | 
  'Shutdown' | 
  'Error' | 
  'Unknown';

// Consolidated format for all agent updates
export interface AgentUpdate {
  // Update type is a category of message from backend (step, status, result, error, etc.)
  update_type: string;
  message: string;
  timestamp: string;
  data: {
    [key: string]: any;
    // When update_type is "step", data will contain the actual AgentStepType
    step_type?: AgentStepType;
  };
}

// Data structure for MCP WebSocket data
interface MCPDataState {
  result?: string;
  synthesis?: string;
  [key: string]: any;
}

// Track active WebSocket connections globally to prevent duplicates
const activeWebSockets: Record<string, WebSocket> = {};

// Track websocket status to avoid reconnecting finished queries
const queryStatusMap: Record<string, AgentStepType | 'idle'> = {};

/**
 * WebSocket hook for connecting to MCP Agent WebSocket
 * This follows MCP Agent's patterns for real-time updates
 * @param queryId The query ID to connect to
 * @param conversationId Optional conversation ID to associate with this WebSocket
 */
export const useAgentWebSocket = (queryId: string, conversationId?: string) => {
  const [socket, setSocket] = useState<WebSocket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<AgentStepType | 'idle'>('idle');
  const [mcpData, setMcpData] = useState<MCPDataState | null>(null);
  const [retryCount, setRetryCount] = useState(0);
  const maxRetries = 3;
  
  // Add state for latest step data for direct rendering in chat
  const [latestStepData, setLatestStepData] = useState<any>(null);
  
  // Ref to track if the component is mounted
  const isMounted = useRef(true);
  useEffect(() => {
    isMounted.current = true;
    return () => { isMounted.current = false; };
  }, []);
  
  // Explicitly close and clean up a WebSocket connection
  const closeWebSocket = useCallback((id: string = queryId, reason: string = "unknown") => {
    if (!id) return false;
    
    const wsInstance = activeWebSockets[id];
    console.log(`Explicitly closing WebSocket for query ${id}. Reason: ${reason}. Instance exists: ${!!wsInstance}, State: ${wsInstance?.readyState}`);
    
    if (wsInstance) {
      // Remove listeners to prevent further actions after close starts
      wsInstance.onmessage = null;
      wsInstance.onerror = null;
      wsInstance.onclose = null; 
      wsInstance.onopen = null;

      // Only attempt to send close and call close if OPEN or CONNECTING
      if (wsInstance.readyState === WebSocket.OPEN) {
        try {
          console.log(`Sending close message for query ${id}`);
          wsInstance.send(JSON.stringify({ type: 'close' }));
        } catch (e) {
          console.warn(`Error sending close message for query ${id}:`, e);
        }
        try {
          console.log(`Calling wsInstance.close() for query ${id}`);
          wsInstance.close(1000, `Query completed or component unmounted: ${reason}`); // Use code 1000 for normal closure
        } catch (e) {
          console.warn(`Error calling wsInstance.close() for query ${id}:`, e);
        }
      } else if (wsInstance.readyState === WebSocket.CONNECTING) {
         try {
          console.log(`Calling wsInstance.close() on CONNECTING socket for query ${id}`);
          wsInstance.close(1000, `Closing connecting socket: ${reason}`);
        } catch (e) {
          console.warn(`Error calling wsInstance.close() on CONNECTING socket for query ${id}:`, e);
        }
      }
    }

    // Always remove from tracking maps regardless of current state
    if (activeWebSockets[id]) {
      delete activeWebSockets[id];
      console.log(`Removed WebSocket reference for query ${id} from activeWebSockets`);
    }
    queryStatusMap[id] = 'Finished'; // Mark as finished in status map
    console.log(`Marked query ${id} as Finished in queryStatusMap`);

    // If this is the current socket managed by the hook, reset the hook's state
    if (socket && socket === wsInstance) {
      if (isMounted.current) {
        setSocket(null);
        setIsConnected(false);
        setStatus('idle');
        console.log(`Hook state reset for query ${id}`);
      }
    }
    
    return true;
  }, [queryId, socket]);

  useEffect(() => {
    let keepAliveInterval: number | null = null;
    let reconnectTimeout: number | null = null;
    let currentWsInstance: WebSocket | null = null;
    
    // Reset state when queryId changes *before* connecting
    if (queryId) {
      console.log(`Query ID changed to ${queryId}, resetting state.`);
      setStatus('idle');
      setError(null);
      setMcpData(null);
      setLatestStepData(null);
      setIsConnected(false);
      setSocket(null);
      setRetryCount(0);
    } else {
      // If queryId becomes null/empty, ensure cleanup
      if (socket) closeWebSocket(queryId, "queryId became null");
      return; // Don't proceed if no queryId
    }

    const connectWebSocket = () => {
      // Double check queryId exists before proceeding
      if (!queryId) {
        console.log('connectWebSocket called without queryId, aborting.');
        return;
      }

      // Check if this query is already finished/completed
      if (queryStatusMap[queryId] === 'Finished' || queryStatusMap[queryId] === 'Error') {
        console.log(`Query ${queryId} is already finished/errored (${queryStatusMap[queryId]}), not connecting.`);
        // Ensure hook state reflects finished status
        if (isMounted.current) {
          setStatus(queryStatusMap[queryId]); 
          setIsConnected(false);
          setSocket(null);
        }
        return;
      }

      // If this query ID already has an active connection, log it but potentially take over?
      // For now, we assume the previous component managing this queryId should have cleaned up.
      if (activeWebSockets[queryId]) {
        console.warn(`Query ${queryId} already has an active WebSocket managed elsewhere. Attempting to take over.`);
        // Force close the old one before creating a new one? Risky.
        // Let's just proceed, the new one will overwrite in activeWebSockets map.
      }

      try {
        // Clear any existing intervals/timeouts from previous attempts for this queryId
        if (keepAliveInterval) clearInterval(keepAliveInterval);
        if (reconnectTimeout) clearTimeout(reconnectTimeout);

        console.log(`Creating new WebSocket connection for query ${queryId}`);

        // Create WebSocket connection URL
        const wsUrl = import.meta.env.VITE_API_URL || 'http://localhost:8001';
        let endpoint = `/api/v1/agents/ws/mcp-agent/${queryId}`;
        if (conversationId) {
          endpoint += `?conversation_id=${conversationId}`;
        }
        const baseWsUrl = wsUrl.replace(/^http/, 'ws');
        const wsEndpoint = baseWsUrl.replace(/\/api\/v1\/?$/, '') + endpoint;
        
        console.log(`Connecting to WebSocket endpoint: ${wsEndpoint}`);
        
        // Create the WebSocket instance
        const wsInstance = new WebSocket(wsEndpoint);
        currentWsInstance = wsInstance; // Track the instance for this effect scope
        activeWebSockets[queryId] = wsInstance; // Store globally
        if (isMounted.current) setSocket(wsInstance); // Update state if mounted
        
        // Set up event listeners
        wsInstance.onopen = () => {
          if (!isMounted.current || currentWsInstance !== wsInstance) return; // Stale event?
          console.log(`✅ MCP WebSocket connected for query ${queryId}`);
          setIsConnected(true);
          setError(null);
          setStatus('Running');
          queryStatusMap[queryId] = 'Running';
          setRetryCount(0); // Reset retry count
          
          // Send initial message
          try {
            wsInstance.send(JSON.stringify({ type: 'init', queryId }));
            console.log(`Sent init message for query ${queryId}`);
          } catch (initError) {
            console.warn('Could not send initial message:', initError);
          }
          
          // Set up keep alive ping
          keepAliveInterval = window.setInterval(() => {
            if (wsInstance && wsInstance.readyState === WebSocket.OPEN) {
              try {
                wsInstance.send(JSON.stringify({ type: 'ping' }));
              } catch (pingError) {
                console.warn(`Failed to send ping for ${queryId}:`, pingError);
                // Consider closing if ping fails repeatedly
              }
            }
          }, 30000);
        };

        wsInstance.onmessage = (event) => {
          if (!isMounted.current || currentWsInstance !== wsInstance) return; // Stale event?
          
          // --- ADDED: Handle non-JSON messages (like ping/pong) --- 
          if (typeof event.data !== 'string') {
            console.log(`Received non-string WebSocket message for ${queryId}, ignoring.`);
            return;
          }
          if (event.data === "pong" || event.data === "ping") {
            console.log(`Received ${event.data} for ${queryId}, ignoring.`); 
            return;
          }
          // --- END ADDED ---
          
          try {
            // Attempt to parse only if it wasn't ping/pong
            const data = JSON.parse(event.data);
            console.log(`🔊 MCP WebSocket message received for query ${queryId}:`, data);
            
            // Handle consolidated update format
            if (data.update_type) {
              const update = data as AgentUpdate;
              setLatestStepData({
                step_type: update.data?.step_type || update.update_type,
                message: update.message,
                agent_name: update.data?.agent_name,
                server_name: update.data?.server_name,
                tool_name: update.data?.tool_name,
                timestamp: update.timestamp,
                raw_data: update.data,
                queryId: queryId
              });

              let currentStatus: AgentStepType | 'idle' = 'Running';

              // Determine status based on message, but DON'T close yet based on step_type
              if (update.update_type === "result") {
                  currentStatus = 'Finished'; // Mark as finished based on result type
                  if (update.data.result || update.data.synthesis) {
                    setMcpData({ result: update.data.result || update.message, synthesis: update.data.synthesis, ...update.data });
                  }
              } else if (update.update_type === "error") {
                  currentStatus = 'Error'; // Mark as error based on error type
                  setError(update.message);
              } else if (update.update_type === "step") {
                  // Use step_type for status, but it no longer closes the connection directly
                  const stepType = update.data?.step_type;
                  if (stepType === 'Error') { // Allow step_type: Error to propagate
                      currentStatus = 'Error';
                      setError(update.message || 'Error reported via step type');
                  } else { 
                      // For all other steps (including Finished step_type), keep status Running
                      currentStatus = 'Running';
                  }
              } else if (update.update_type === "status") {
                  if (update.data?.status === "processing") currentStatus = 'Running';
                  else if (update.data?.status === "completed") {
                      // Treat backend "completed" status as Finished, but DON'T close here
                      currentStatus = 'Finished';
                  } else currentStatus = 'Unknown';
              } else {
                   currentStatus = 'Running'; // Default to running
              }

              // Update status state and map
              if (isMounted.current) setStatus(currentStatus);
              queryStatusMap[queryId] = currentStatus;

              // If finished or errored based on *update_type*, initiate close
              if (update.update_type === 'result' || update.update_type === 'error') {
                  console.log(`🔚 Query ${queryId} received final update_type ${update.update_type}, initiating close.`);
                  // Use the dedicated close function
                  closeWebSocket(queryId, `Query final update_type ${update.update_type}`);
              }
            }
          } catch (err) {
            console.error(`Error parsing WebSocket message for ${queryId}:`, err);
          }
        };

        wsInstance.onclose = (event) => {
          if (currentWsInstance !== wsInstance) return; // Stale event
          console.log(`❌ MCP WebSocket disconnected for query ${queryId}. Code: ${event.code}, Reason: ${event.reason}`);
          
          // Clear keep-alive interval
          if (keepAliveInterval) clearInterval(keepAliveInterval);
          keepAliveInterval = null;

          // Clean up the global reference ONLY if it's this instance
          if (activeWebSockets[queryId] === wsInstance) {
            delete activeWebSockets[queryId];
            console.log(`Removed WebSocket reference for query ${queryId} during onclose`);
          }

          // Update state if component is still mounted
          if (isMounted.current) {
            setIsConnected(false);
            setSocket(null); 
            // Don't reset status here, it might have been set to Finished/Error
          }
          
          // Reconnection logic
          const isFinished = queryStatusMap[queryId] === 'Finished' || queryStatusMap[queryId] === 'Error';
          const wasCleanClose = event.code === 1000;

          if (!isFinished && !wasCleanClose && retryCount < maxRetries) {
            const retryDelay = Math.pow(2, retryCount) * 1000;
            console.log(`Attempting to reconnect WebSocket ${queryId} in ${retryDelay}ms (retry ${retryCount + 1}/${maxRetries})`);
            reconnectTimeout = window.setTimeout(() => {
              if (isMounted.current) setRetryCount(prev => prev + 1);
              // Check status *again* before reconnecting
              if (queryStatusMap[queryId] !== 'Finished' && queryStatusMap[queryId] !== 'Error') {
                 connectWebSocket();
              } else {
                console.log(`Query ${queryId} finished/errored before reconnect attempt.`);
              }
            }, retryDelay);
          } else if (!isFinished && !wasCleanClose) {
            console.log(`WebSocket ${queryId} reconnection attempts exhausted.`);
             if (isMounted.current) setError('Connection lost. Max retries reached.');
             queryStatusMap[queryId] = 'Error'; // Mark as error if retries exhausted
             if (isMounted.current) setStatus('Error'); 
          } else {
            console.log(`WebSocket ${queryId} closed. Clean: ${wasCleanClose}, Finished: ${isFinished}. No reconnect needed.`);
            // Ensure status reflects the final state if closed cleanly but not marked finished yet
            if(wasCleanClose && !isFinished && isMounted.current) {
               setStatus('idle'); // Or perhaps Error if unexpected clean close?
               queryStatusMap[queryId] = 'Error'; // Treat unexpected clean close as error
            }
          }
        };

        wsInstance.onerror = (err) => {
          if (currentWsInstance !== wsInstance) return; // Stale event?
          console.error(`❌ MCP WebSocket error for query ${queryId}:`, err);
          if (isMounted.current) {
             setError('WebSocket connection error');
             setStatus('Error');
          }
          queryStatusMap[queryId] = 'Error';
          // The onclose event will likely fire after onerror, handling cleanup/reconnect there.
        };

      } catch (err) {
        console.error(`Error setting up MCP WebSocket for ${queryId}:`, err);
        if (isMounted.current) {
           setError(`Setup error: ${err instanceof Error ? err.message : String(err)}`);
           setStatus('Error');
        }
        queryStatusMap[queryId] = 'Error';
      }
    };

    // Initial connection attempt
    connectWebSocket();

    // Clean up on unmount or when queryId changes
    return () => {
      console.log(`Cleanup effect running for query ${queryId}. Current socket state: ${currentWsInstance?.readyState}`);
      // Use the robust close function
      if (currentWsInstance) {
         closeWebSocket(queryId, "component unmount or queryId change");
      }
      // Clear any pending timeouts
      if (keepAliveInterval) clearInterval(keepAliveInterval);
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [queryId, conversationId]); // Removed dependencies that might cause re-runs incorrectly, rely on queryId change

  // Method to check if a WebSocket exists for a queryId (mainly for debugging)
  const hasActiveWebSocketForQuery = useCallback((id: string) => {
    return !!activeWebSockets[id];
  }, []);

  return {
    socket,
    isConnected,
    error,
    status,
    mcpData,
    latestStepData,
    hasActiveWebSocketForQuery,
    closeWebSocket, 
    // Removed reset as it's handled internally now
    // Keep streamingSteps for backward compatibility but it's empty now
    streamingSteps: []
  };
};

export default useAgentWebSocket; 