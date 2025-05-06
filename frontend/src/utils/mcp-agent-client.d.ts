/**
 * File attachment information
 */
interface MCPAttachment {
  id: string;
  name: string;
  type: string;
  size: number;
  url?: string;
  data?: string;
  file_id?: string;  // Optional alias for id to maintain compatibility with backend expectations
}

/**
 * Backend payload interface - what actually gets sent to the coordinator endpoint
 */
interface MCPBackendPayload {
  // Core request identification
  query_id: string;                    // Unique ID for this request
  session_id?: string;                 // Conversation/session ID for continuity

  // Optional fields based on request type
  workflow_type?: string;              // Only included if explicitly specified
  option_index?: string;               // Only for intention agent requests
  query?: string;                      // Only for direct input in REST mode
  agents?: string[];                   // Optional specific agents to use

  // Context object containing request details
  context: {
    // For user input queries
    query?: string;                    // Regular user input message
    
    // For intention agent options
    text?: string;                     // The option text/title
    description?: string;              // Option description
    from_intention_agent?: boolean;    // Flag for intention agent source
    
    // Attachments
    attachments: MCPAttachment[];
    
    // Any additional context fields
    [key: string]: any;
  }
}

/**
 * Request options for processRequest
 */
interface MCPRequestOptions {
  realtime?: boolean;
  attachments?: MCPAttachment[];
  conversation_id?: string;
  query_id?: string;  // Added to allow passing a consistent query ID
  workflowType?: string;
  sessionId?: string;
  agents?: string[];
  additionalContext?: Record<string, any>;
  fromIntentionAgent?: boolean;
}

/**
 * Processed request data for internal use
 */
interface MCPProcessedRequest {
  query: string;
  intentionOptionId?: string;
  description?: string;
  fromIntentionAgent: boolean;
  conversation_id?: string;
  workflowType?: string;
  agents?: string[];
  attachments?: MCPAttachment[];
  additionalContext?: Record<string, any>;
}

/**
 * Progress callback data
 */
interface MCPProgressData {
  query_id?: string;
  update_type: string;
  agent?: string;
  message?: string;
  timestamp?: number;
  [key: string]: any;
}

/**
 * Completion callback data
 */
interface MCPCompletionData {
  query_id?: string;
  update_type: string;
  result?: string;
  session_id?: string;
  timestamp?: number;
  [key: string]: any;
}

/**
 * Error callback data
 */
interface MCPErrorData {
  query_id?: string;
  update_type: string;
  message?: string;
  error?: string;
  timestamp?: number;
  [key: string]: any;
}

declare class MCPAgentClient {
  constructor(options?: {
    endpoint?: string;
    onProgress?: (data: MCPProgressData) => void;
    onCompleted?: (data: MCPCompletionData) => void;
    onError?: (data: MCPErrorData) => void;
    sessionId?: string;
    forceRestOnly?: boolean;
  });
  
  processRequest(
    requestData: string | {
      id?: string;
      title?: string;
      description?: string;
      query?: string;
    },
    options?: MCPRequestOptions
  ): Promise<any>;
  
  isInitialized: boolean;
  getStatus(): {
    initialized: boolean;
    restOnlyMode: boolean;
    clientId: string;
  };
}

export default MCPAgentClient; 