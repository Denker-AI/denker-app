/**
 * MCP Agent Client
 * 
 * This module provides functions to interact with the MCP Agent coordinator API.
 * Supports both RESTful API calls and WebSocket connections for real-time updates.
 */

import { getLocalApiUrl } from '../services/apiService';
import { getUserInfoCached } from './user-info-cache';
import { getCachedAccessToken } from './token-cache';

// Default API endpoint
const BASE_URL = getLocalApiUrl() || 'http://localhost:9001/api/v1';
const COORDINATOR_ENDPOINT = `${BASE_URL}/agents/coordinator/mcp-agent`;
const LOCAL_LOGIN_ENDPOINT = `${BASE_URL}/agents/auth/local-login`;

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

// WebSocket URL - dynamically determine based on current hostname
const getWebSocketBaseUrl = () => {
  // If environment variable exists, use it
  if (import.meta.env.VITE_LOCAL_WS_URL) {
    return import.meta.env.VITE_LOCAL_WS_URL;
  }
  // Otherwise use current hostname
  const hostname = window.location.hostname || 'localhost';
  return `ws://${hostname}:9001`;
};

const WEBSOCKET_BASE_URL = getWebSocketBaseUrl();
// Updated to use only the FastAPI versioned WebSocket endpoint
const WEBSOCKET_ENDPOINT = `${WEBSOCKET_BASE_URL}/api/v1/agents/ws/mcp-agent`;

// Health check URL - should point to FastAPI health endpoint
const HEALTH_CHECK_URL = `${BASE_URL}/health`;

// Debug API configuration - log detailed connection info
console.log('MCP Agent API configuration:', {
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

// WebSocket retry settings
const WEBSOCKET_RETRY_DELAY = 1000; // 1 second
const WEBSOCKET_MAX_RETRIES = 3;

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
    
    // Default not logged in
    this.isLoggedIn = false;
    this.userId = null;
    this.userToken = null;
    
    // Mark as initialized immediately - we'll check backend availability on demand
    this._initialized = true;
    
    // Auto-login for development mode
    if (import.meta.env.DEV) {
      this._devModeLogin();
    }
  }
  
  /**
   * Development mode auto-login
   */
  async _devModeLogin() {
    try {
      console.log('[MCPAgentClient] Using development mode auto-login');
      const result = await this.login('dev-user-id', 'dev-mode-token');
      console.log('[MCPAgentClient] Development mode login result:', result);
      return result;
    } catch (error) {
      console.warn('[MCPAgentClient] Development mode login failed:', error);
      return false;
    }
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
      isLoggedIn: this.isLoggedIn,
      userId: this.userId ? this.userId.substring(0, 8) + '...' : null,
    };
    
    return status;
  }
  
  /**
   * Login to the local backend
   * @param {string} userId - User ID
   * @param {string} token - Authentication token
   * @returns {Promise<boolean>} - Whether login was successful
   */
  async login(userId, token) {
    try {
      console.log(`[MCPAgentClient] Logging in with user ID: ${userId}`);
      
      // For development mode, provide a simplified experience that avoids backend errors
      if (import.meta.env.DEV && (!token || token === 'dev-mode-token')) {
        console.log('[MCPAgentClient] Using dev mode simplified login');
        this.isLoggedIn = true;
        this.userId = userId || 'dev-user-id';
        this.userToken = token || 'dev-mode-token';
        return true;
      }
      
      const response = await fetch(LOCAL_LOGIN_ENDPOINT, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          user_id: userId,
          token: token
        }),
        credentials: 'include'
      });
      
      if (!response.ok) {
        // Try to parse error from backend if possible
        let errorMsg = `Login failed: ${response.status} ${response.statusText}`;
        try {
            const errorData = await response.json();
            errorMsg = errorData.detail || errorData.message || errorMsg;
        } catch (e) { /* ignore parsing error */ }
        
        // Don't throw error for common startup scenarios
        if (response.status === 503 || response.status === 502 || response.status === 0) {
          console.warn(`[MCPAgentClient] Backend not ready yet (${response.status}), this is normal during startup`);
          // For development, still allow operations
          if (import.meta.env.DEV) {
            console.log('[MCPAgentClient] Using dev mode login fallback for startup timing');
            this.isLoggedIn = true;
            this.userId = userId || 'dev-user-id';
            this.userToken = token || 'dev-mode-token';
            return true;
          }
          return false; // Return false instead of throwing error
        }
        
        throw new Error(errorMsg);
      }
      
      // If response.ok is true, consider the login successful at this point
      // The actual content of 'result' can be used for logging or further details if needed
      const result = await response.json();
      // console.log('[MCPAgentClient] Login API call successful, response data:', result);

        this.isLoggedIn = true;
        this.userId = userId;
        this.userToken = token;
      console.log('[MCPAgentClient] Successfully logged in to local backend and updated client state.');
        return true;
    } catch (error) {
      console.error('Error logging in to local backend:', error);
      
      // For development, still allow operations
      if (import.meta.env.DEV) {
        console.log('[MCPAgentClient] Using dev mode login fallback after error');
        this.isLoggedIn = true;
        this.userId = userId || 'dev-user-id';
        this.userToken = token || 'dev-mode-token';
        return true;
      }
      
      this.isLoggedIn = false;
      return false;
    }
  }
  
  /**
   * Process a request using the MCP Agent coordinator
   * @param {string|object} requestData - Either a string query or an object with query/options data
   * @param {object} options - Additional options for the request
   * @returns {Promise<object>} - Promise that resolves with the response
   */
  async processRequest(requestData, options = {}) {
    // Check if logged in first
    if (!this.isLoggedIn) {
      try {
        // Auto-login with electron credentials if available
        if (window.electron?.getAccessToken) {
          try {
            const token = await getCachedAccessToken(); // Use cached token system
            const user = await getUserInfoCached(); // Use cached user info to prevent Auth0 calls
            if (token && user && (user.id || user.sub)) {
              const userId = user.id || user.sub;
              await this.login(userId, token);
            }
          } catch (error) {
            console.warn('Auto-login failed:', error);
            // For development mode, still allow operations with dev credentials
            if (import.meta.env.DEV) {
              await this._devModeLogin();
            }
          }
        } else if (import.meta.env.DEV) {
          // Development mode without electron
          await this._devModeLogin();
        }
      } catch (loginError) {
        console.error('[MCPAgentClient] Error during login attempt:', loginError);
        if (!import.meta.env.DEV) {
          throw new Error(`Authentication required: ${loginError.message}`);
        }
        // In dev mode, continue anyway
      }
    }

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
      
      // Create headers
      const headers = {
        'Content-Type': 'application/json',
      };
      
      // Make the initial request to the coordinator endpoint to kick off the process
      const response = await fetch(`${COORDINATOR_ENDPOINT}`, {
        method: 'POST',
        headers,
        body: JSON.stringify(payload),
        signal: AbortSignal.timeout(10000), // 10 second timeout
        credentials: 'include', // Include cookies in the request
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
      
      // Create headers
      const headers = {
        'Content-Type': 'application/json',
      };
      
      // Send the request to the API
      const response = await fetch(`${COORDINATOR_ENDPOINT}`, {
        method: 'POST',
        headers,
        body: JSON.stringify(payload),
        signal: AbortSignal.timeout(60000), // 60 second timeout
        credentials: 'include', // Include cookies in the request
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