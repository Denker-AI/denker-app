import axios, { AxiosInstance, AxiosResponse, CreateAxiosDefaults } from 'axios';
import type { IntentionRequest, IntentionResponse } from '../types/types';
import { CircuitBreaker } from './circuitBreaker';

// Initialize circuit breaker
const circuitBreaker = new CircuitBreaker({
  failureThreshold: 5,
  resetTimeout: 30000
});

// Expose the circuit breaker reset function globally
// @ts-ignore - Add to window object
window.resetCircuitBreaker = () => {
  console.log('Manual circuit breaker reset triggered');
  circuitBreaker.forceReset();
};

// Define custom API interface extending AxiosInstance
interface CustomAPI extends AxiosInstance {
  processMCPCoordinator: (data: any) => Promise<AxiosResponse>;
  checkCoordinatorStatus: (queryId: string) => Promise<AxiosResponse>;
  uploadFile: (formData: FormData, config?: any) => Promise<AxiosResponse>;
  sendMessage: (text: string, conversationId: string, attachments?: any[]) => Promise<AxiosResponse>;
}

// Define the base URL constant for clarity
const getApiBaseUrl = () => {
  // Check if in Electron context
  if (window.electron) {
    // Use Electron's environment variables
    return window.electron.getEnvVars().VITE_API_URL;
  }
  // Fallback to Vite env vars or default
  return import.meta.env.VITE_API_URL || 'http://localhost:8001/api/v1';
};

// Create axios instance with type declaration for custom methods
const api = axios.create({
  baseURL: getApiBaseUrl(), // Use the dynamic function
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 15000, // 15 seconds timeout
}) as CustomAPI;

// Add coordinator endpoint to the axios instance
api.processMCPCoordinator = (data: any) => {
  // Increase timeout specifically for the coordinator endpoint
  return api.post('/agents/coordinator/mcp-agent', data, {
    timeout: 60000 // 60 seconds timeout for this specific endpoint
  });
};

// Add coordinator status check method
api.checkCoordinatorStatus = (queryId: string) => {
  return api.get(`/agents/status/${queryId}`);
};

// Add file upload method
api.uploadFile = (formData: FormData, config?: any) => {
  return api.post('/files/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    ...config
  });
};

// Add sendMessage method CORRECTLY using the api instance
api.sendMessage = (text: string, conversationId: string, attachments: any[] = []) => {
  // Use the 'api' instance which has the baseURL configured
  return api.post(`/conversations/${conversationId}/messages`, {
    content: text,
    role: 'user', // Assuming messages sent via this are always from the user
    attachments: attachments
  });
};

// Add request interceptor for circuit breaker
api.interceptors.request.use(
  async (config) => {
    // If circuit is open, reject the request
    if (circuitBreaker.check()) {
      console.log('Circuit breaker: blocking request to', config.url);
      return Promise.reject(new Error('Circuit is open - API is currently unavailable'));
    }
    
    // --- MODIFIED: Get token via IPC ---
    try {
      const token = await window.electron?.getAccessToken(); 
      if (token) {
        console.log(`[API Interceptor] Adding token to ${config.method?.toUpperCase()} ${config.url}`);
        config.headers.Authorization = `Bearer ${token}`;
      } else {
        console.warn(`[API Interceptor] No token available for ${config.method?.toUpperCase()} ${config.url}. Request may fail.`);
        // If the request requires auth and there's no token, the backend should return 401.
        // Remove any potentially stale Authorization header
        delete config.headers.Authorization;
      }
    } catch (error) {
      console.error('[API Interceptor] Error getting access token via IPC:', error);
      // Proceed without token, let backend handle potential 401
      delete config.headers.Authorization;
    }
    // --- END MODIFICATION ---
    
    return config;
  },
  (error) => {
    // Do something with request error
    return Promise.reject(error);
  }
);

// Add response interceptor for circuit breaker
api.interceptors.response.use(
  (response) => {
    // On successful response, record success
    circuitBreaker.success();
    return response;
  },
  (error) => {
    // On failure, record failure
    circuitBreaker.failure();
    return Promise.reject(error);
  }
);

// Enhanced API hook with retry logic for coordinator status
export const useEnhancedApi = () => {
  // ... rest of file ...
};

// Export the configured api instance directly
export default api;