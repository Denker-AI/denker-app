export interface AgentUpdate {
  update_type: string;
  message: string;
  timestamp: string;
  data?: {
    step_type?: string;
    agent_name?: string;
    server_name?: string;
    tool_name?: string;
    tool_description?: string;
    tool_input?: any;
    tool_output?: any;
    status?: string;
    input_id?: string;
    required?: boolean;
    error?: string;
    [key: string]: any; // Allow for additional fields we might not have explicitly typed
  };
  [key: string]: any; // Allow for additional fields at the top level
}

export interface StepData {
  step_type: string;
  message: string;
  agent_name?: string;
  server_name?: string;
  tool_name?: string;
  description?: string;
  timestamp?: string;
  raw_data?: any; // Store the full data object for debugging
}

export class WebSocketService {
  constructor(url: string, options: any = {}) {
    this.url = url || this.getWebsocketUrl();
    this.options = options;
    this.reconnectAttempts = 0;
    this.status = 'disconnected';
    this.messageQueue = [];
    this.listeners = {
      message: [],
      open: [],
      close: [],
      error: []
    }
  }

  // ...existing code...

  private processWebSocketMessage(event: MessageEvent) {
    try {
      // Skip pong messages
      if (event.data === "pong") return;
      
      // Parse JSON data
      const data = JSON.parse(event.data);
      console.log(`⚡ WebSocket data received:`, data);
      
      // Handle consolidated update format
      if (data.update_type) {
        const update = data as AgentUpdate;
        
        // Process based on update type
        switch(update.update_type) {
          case "status":
            console.log(`🟢 WebSocket status update: ${update.message}`);
            // Status updates may inform about the connection state
            if (update.data?.status === "ready") {
              this.connectionStatus = "connected";
              this.eventEmitter.emit('status', { status: 'connected' });
            }
            break;
            
          case "step":
            console.log(`🔄 Agent step update: ${update.message}`);
            // For step updates, extract the step data and emit it
            if (update.data) {
              this.eventEmitter.emit('step', {
                step_type: update.data.step_type || 'Unknown',
                message: update.message,
                agent_name: update.data.agent_name,
                server_name: update.data.server_name, 
                tool_name: update.data.tool_name,
                description: update.data.tool_description,
                timestamp: update.timestamp,
                raw_data: update.data
              });
            }
            break;
            
          case "result":
            console.log(`✅ Query result received: ${update.message.substring(0, 50)}...`);
            // Results indicate the query is complete
            this.eventEmitter.emit('result', {
              result: update.message,
              timestamp: update.timestamp,
              data: update.data
            });
            this.connectionStatus = "completed";
            break;
            
          case "error":
            console.log(`❌ WebSocket error: ${update.message}`);
            // Handle error messages
            this.eventEmitter.emit('error', {
              message: update.message,
              error: update.data?.error || 'unknown_error',
              timestamp: update.timestamp
            });
            this.connectionStatus = "error";
            break;
            
          case "human_input":
            console.log(`👤 Human input request: ${update.message}`);
            // Handle requests for human input
            this.eventEmitter.emit('human_input', {
              message: update.message,
              input_id: update.data?.input_id,
              required: update.data?.required !== false, // Default to true
              timestamp: update.timestamp
            });
            break;
            
          default:
            console.log(`📦 Unhandled update type: ${update.update_type}`);
            // For any other update types, just pass them through
            this.eventEmitter.emit('update', update);
        }
      } else {
        // Legacy format or unknown format
        console.log('⚠️ Received WebSocket message with unknown format');
        this.eventEmitter.emit('message', data);
      }
    } catch (error) {
      console.error('Error processing WebSocket message:', error);
      this.eventEmitter.emit('error', {
        message: 'Error processing WebSocket message',
        error: 'parse_error',
        originalError: error
      });
    }
  }

  // Get the WebSocket URL from environment variables or Electron
  private getWebsocketUrl() {
    // Check if in Electron context
    if (window.electron) {
      // Use Electron's environment variables
      return window.electron.getEnvVars().VITE_WS_URL.replace('http', 'ws').replace('/api/v1', '');
    }
    // Fallback to Vite env vars or convert API URL to WS URL
    const wsUrl = import.meta.env.VITE_WS_URL;
    if (wsUrl) return wsUrl;
    
    // If no WS URL is provided, convert API URL to WS URL
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8001/api/v1';
    return apiUrl.replace('http', 'ws').replace('/api/v1', '');
  }
} 