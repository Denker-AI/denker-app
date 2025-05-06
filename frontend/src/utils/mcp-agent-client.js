/**
 * MCP Agent Client
 * 
 * This module provides functions to interact with the MCP Agent coordinator API.
 * Supports both RESTful API calls and WebSocket connections for real-time updates.
 */

// Generate a unique client ID for this session
const generateClientId = () => {
  return 'client_' + Math.random().toString(36).substring(2, 15);
};

// Generate a UUID v4 for unique request IDs
const generateUUID = () => {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
    const r = Math.random() * 16 | 0;
    const v = c === 'x' ? r : (r & 0x3 | 0x8);
    return v.toString(16);
  });
};

// Default client ID for this session
const DEFAULT_CLIENT_ID = generateClientId();

// API endpoint configurations using Vite env variables 
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001/api/v1';
// Get base URL without /api/v1 suffix for coordinator endpoints
const BASE_URL = API_BASE_URL.replace(/\/api\/v1\/?$/, '');
// Updated to use only the FastAPI versioned endpoint
const COORDINATOR_ENDPOINT = `${API_BASE_URL}/agents/coordinator/mcp-agent`;

// WebSocket URL - dynamically determine based on current hostname
const getWebSocketBaseUrl = () => {
  // If environment variable exists, use it
  if (import.meta.env.VITE_WS_URL) {
    return import.meta.env.VITE_WS_URL;
  }
  
  // Otherwise use current hostname
  const hostname = window.location.hostname || 'localhost';
  return `ws://${hostname}:8001`;
};

const WEBSOCKET_BASE_URL = getWebSocketBaseUrl();
// Updated to use only the FastAPI versioned WebSocket endpoint
const WEBSOCKET_ENDPOINT = `${WEBSOCKET_BASE_URL}/api/v1/agents/ws/mcp-agent`;

// Health check URL - should point to FastAPI health endpoint
const HEALTH_CHECK_URL = `${API_BASE_URL}/health`;

// Debug API configuration - log detailed connection info
console.log('MCP Agent API configuration:', {
  API_BASE_URL,
  BASE_URL,
  COORDINATOR_ENDPOINT,
  WEBSOCKET_BASE_URL,
  WEBSOCKET_ENDPOINT,
  HEALTH_CHECK_URL
});

// Check if API is initialized
let isApiInitialized = false;

// Debug flag to enable REST-only mode
let forceRestOnlyMode = false; // Enable WebSocket communication

/**
 * MCP Agent Client class for interacting with the coordinator
 */
class MCPAgentClient {
  constructor(options = {}) {
    this.clientId = options.clientId || DEFAULT_CLIENT_ID;
    this.sessionId = null;
    this.forceRestOnlyMode = options.forceRestOnly || forceRestOnlyMode;
    this.pendingRequests = {};
    this.requests = {};
    this.callbacks = {
      onProgress: options.onProgress || (() => {}),
      onCompleted: options.onCompleted || (() => {}),
      onError: options.onError || (() => {}),
    };
    
    // Mark as initialized immediately - we'll check backend availability on demand
    this._initialized = true;
  }
  
  /**
   * Get the status of the client
   * @returns {Object} Status information
   */
  getStatus() {
    const status = {
      initialized: this.isInitialized,
      restOnlyMode: this.forceRestOnlyMode,
      clientId: this.clientId,
    };
    
    return status;
  }
  
  /**
   * Process a request using the MCP Agent coordinator
   * @param {string|object} requestData - Either a string query or an object with query/options data
   * @param {object} options - Additional options for the request
   * @returns {Promise<object>} - Promise that resolves with the response
   */
  async processRequest(requestData, options = {}) {
    // If requestData is a string, treat it as a direct query from input box
    if (typeof requestData === 'string') {
      requestData = {
        query: requestData,
        // Copy any options passed in
        ...options,
        // Flag this as not from intention agent
        fromIntentionAgent: false 
      };
    } 
    // If requestData appears to be an intention agent option
    else if (requestData.id && requestData.title) {
      requestData = {
        intentionOptionId: requestData.id,
        query: requestData.title,
        description: requestData.description || '',
        fromIntentionAgent: true,
        // Copy any options passed in
        ...options
      };
    }

    // Generate a unique request ID
    // Use the query_id from options if provided, otherwise generate a new one
    const requestId = requestData.query_id || generateUUID();
    if (requestData.query_id) {
      console.log(`Using provided query_id: ${requestId}`);
    } else {
      console.log(`Generated new query_id: ${requestId}`);
    }
    console.log(`Processing request ${requestId}:`, requestData);

    // Create a new request object for tracking
    const request = {
      id: requestId,
      status: 'pending',
      data: requestData,
      timestamp: Date.now(),
      progress: [],
      result: null,
      error: null,
    };

    // Store the request
    this.requests[requestId] = request;

    try {
      // Try WebSocket first if not in REST-only mode
      if (!this.forceRestOnlyMode) {
        try {
          // We'll always try WebSocket mode first for each request (per-query WebSockets)
          return await this._processWebSocketRequest(requestId, requestData);
        } catch (error) {
          console.warn('WebSocket connection failed, falling back to REST:', error);
          // Continue to REST fallback below
        }
      }

      // Fall back to REST if WebSocket not available or failed
      return await this._processRestRequest(requestId, requestData);
    } catch (error) {
      this._handleRequestError(requestId, error);
      
      // If the error is a network or server error, enhance the error message
      if (error.message.includes('fetch') || 
          error.message.includes('network') || 
          error.message.includes('Backend') ||
          error.message.includes('API')) {
        throw new Error(`Backend service unavailable: ${error.message}`);
      }
      
      throw error;
    }
  }

  /**
   * Process a request using WebSocket (modified to only initiate via HTTP POST)
   * @param {string} requestId - The unique request ID
   * @param {object} requestData - The request data
   * @returns {Promise<object>} - Promise that resolves with the initial HTTP response
   * @private
   */
  async _processWebSocketRequest(requestId, requestData) {
    try {
      // Update request status (optional, could be handled by caller)
      this.requests[requestId].status = 'initiating'; // Changed status
      
      // Prepare the request payload (same as before)
      const payload = {
        query_id: requestId,
        session_id: requestData.conversation_id || this.sessionId,
        context: {}
      };
      if (requestData.workflowType) payload.workflow_type = requestData.workflowType;
      payload.context.query = requestData.query;
      payload.context.from_intention_agent = requestData.fromIntentionAgent;
      payload.context.conversation_id = requestData.conversation_id || this.sessionId;
      payload.context.message_id = requestData.message_id;
      if (requestData.description) payload.context.description = requestData.description;
      payload.context.attachments = requestData.attachments || [];
      if (requestData.additionalContext) payload.context = { ...payload.context, ...requestData.additionalContext };
      if (requestData.agents && requestData.agents.length > 0) payload.agents = requestData.agents;
      
      console.log(`Initiating WebSocket process via HTTP POST ${requestId}:`, payload);
      
      // Make the initial request to the coordinator endpoint to kick off the process
      const response = await fetch(`${COORDINATOR_ENDPOINT}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        signal: AbortSignal.timeout(10000), // 10 second timeout
      });
      
      if (!response.ok) {
        // Try to get error details from response body
        let errorBody = {};
        try {
          errorBody = await response.json();
        } catch (e) { /* Ignore if body isn't valid JSON */ }
        
        console.error(`HTTP POST initialization error: ${response.status} ${response.statusText}`, errorBody);
        throw new Error(`HTTP POST initialization error: ${response.status} ${response.statusText}`);
      }
      
      const result = await response.json();
      console.log(`Request ${requestId} initiated via HTTP POST with response:`, result);
      
      // Mark status as processing, as the backend will now handle it via WebSocket
      this.requests[requestId].status = 'processing'; 
      
      // Return the initial response from the HTTP POST
      // Subsequent updates will come via the WebSocket managed by useAgentWebSocket
      return result;
      
    } catch (error) {
      // Update request status on error
      if (this.requests[requestId]) {
        this.requests[requestId].status = 'error';
        this.requests[requestId].error = error.message;
      }
      // Call the main error handler (which includes the callback)
      this._handleRequestError(requestId, error);
      // Re-throw the error so the caller knows it failed
      throw error;
    }
  }

  /**
   * Process a request using REST API
   * @param {string} requestId - The unique request ID
   * @param {object} requestData - The request data
   * @returns {Promise<object>} - Promise that resolves with the response
   * @private
   */
  async _processRestRequest(requestId, requestData) {
    try {
      // Update request status
      this.requests[requestId].status = 'processing';
      
      // Prepare the request payload with consistent format for both intention and input box sources
      const payload = {
        query_id: requestId,
        session_id: requestData.conversation_id || this.sessionId,
        context: {}
      };
      
      // Only add workflow_type if explicitly provided
      if (requestData.workflowType) {
        payload.workflow_type = requestData.workflowType;
      }
      
      // Add the user query in a consistent location
      payload.context.query = requestData.query;
      payload.context.from_intention_agent = requestData.fromIntentionAgent;
      
      // Add conversation reference for memory persistence
      payload.context.conversation_id = requestData.conversation_id || this.sessionId;
      payload.context.message_id = requestData.message_id;
      
      if (requestData.description) {
        payload.context.description = requestData.description;
      }
      
      // For REST API backward compatibility
      if (requestData.fromIntentionAgent) {
        payload.option_index = requestData.intentionOptionId;
      } else {
        payload.query = requestData.query; // Top-level query for REST API backward compatibility
      }
      
      // Add attachments to context consistently
      payload.context.attachments = requestData.attachments || [];
      
      // Add any additional context data
      if (requestData.additionalContext) {
        payload.context = {
          ...payload.context,
          ...requestData.additionalContext
        };
      }
      
      // Add specific agents if provided
      if (requestData.agents && requestData.agents.length > 0) {
        payload.agents = requestData.agents;
      }
      
      console.log(`Sending REST request ${requestId}:`, payload);
      
      // Send the request to the API
      const response = await fetch(`${COORDINATOR_ENDPOINT}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
        signal: AbortSignal.timeout(60000), // 60 second timeout
      });
      
      if (!response.ok) {
        throw new Error(`REST API error: ${response.status} ${response.statusText}`);
      }
      
      const result = await response.json();
      
      // Store session ID if provided
      if (result.session_id) {
        this.sessionId = result.session_id;
      }
      
      // Update the request with the result
      this.requests[requestId].status = 'completed';
      this.requests[requestId].result = result;
      
      console.log(`Request ${requestId} completed:`, result);
      
      return result;
    } catch (error) {
      this._handleRequestError(requestId, error);
      throw error;
    }
  }

  /**
   * Handle a request error, calling the error callback and resolving the promise with an error
   * @param {string} requestId - The ID of the request
   * @param {Error} error - The error that occurred
   * @private
   */
  _handleRequestError(requestId, error) {
    console.error(`Error processing request ${requestId}:`, error);
    
    // Update the request status
    if (this.requests[requestId]) {
      this.requests[requestId].status = 'error';
      this.requests[requestId].error = error.message;
    }
    
    // Call the error callback
    if (typeof this.callbacks.onError === 'function') {
      this.callbacks.onError({
        requestId,
        error: error.message,
        timestamp: Date.now()
      });
    }
  }

  /**
   * Get the initialization status of the client
   * @returns {boolean} True if initialized, false otherwise
   */
  get isInitialized() {
    return !!this._initialized;
  }
  
  /**
   * Set the initialization status
   * @param {boolean} value - The new status
   */
  set isInitialized(value) {
    this._initialized = value;
  }
}

export default MCPAgentClient; 