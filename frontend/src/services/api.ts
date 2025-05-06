import axios, { AxiosInstance, AxiosResponse, CreateAxiosDefaults } from 'axios';
import { useAuth0 } from '@auth0/auth0-react';
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
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001/api/v1';

// Create axios instance with type declaration for custom methods
const api = axios.create({
  baseURL: API_BASE_URL, // Use the defined constant
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
    return config;
  },
  (error) => {
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

// Add auth token to requests
export const useApi = () => {
  const { getAccessTokenSilently, isAuthenticated } = useAuth0();

  // Add auth token to requests
  api.interceptors.request.use(
    async (config) => {
      if (isAuthenticated) {
        try {
          const token = await getAccessTokenSilently();
          if (token) {
            config.headers.Authorization = `Bearer ${token}`;
          }
        } catch (error) {
          console.error('Error getting access token:', error);
        }
      }
      return config;
    },
    (error) => {
      return Promise.reject(error);
    }
  );

  return {
    // Auth endpoints
    login: async () => {
      const token = await getAccessTokenSilently();
      return api.post('/auth/login', { token });
    },
    logout: () => api.post('/auth/logout'),

    // User endpoints
    getUserProfile: () => api.get('/users/profile'),
    updateUserProfile: (data: any) => api.put('/users/profile', data),
    getUserSettings: () => api.get('/users/settings'),
    updateUserSettings: (data: any) => api.put('/users/settings', data),

    // Conversation endpoints
    getConversations: () => api.get('/conversations/list'),
    createConversation: (data: any) => api.post('/conversations/new', data),
    getConversation: (id: string, params?: { limit?: number; before_message_id?: string }) => 
      api.get(`/conversations/${id}`, { params }),
    updateConversation: (id: string, data: any) => api.put(`/conversations/${id}`, data),
    deleteConversation: (id: string) => api.delete(`/conversations/${id}`),
    addMessage: (conversationId: string, data: any) => 
      api.post(`/conversations/${conversationId}/messages`, data),

    // File endpoints
    getFiles: async () => {
      try {
        // Use the new endpoint that filters out deleted files
        const response = await api.get('/files/');
        return response;
      } catch (error) {
        if (axios.isAxiosError(error)) {
          console.error('Error fetching files:', error.response?.data?.detail || error.message);
        } else {
          console.error('Error fetching files:', error);
        }
        throw error;
      }
    },
    uploadFile: async (file: File, query_id?: string | null, message_id?: string | null, cancelToken?: CancelToken, onUploadProgress?: (progressEvent: any) => void) => {
      const formData = new FormData();
      formData.append('file', file);
      
      if (query_id) {
        formData.append('query_id', query_id);
      }
      if (message_id) {
        formData.append('message_id', message_id);
      }
      
      console.log('Uploading file:', file.name, 'with query_id:', query_id, 'message_id:', message_id);

      return api.post('/files/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        timeout: 60000, // 60 seconds
        cancelToken,
        onUploadProgress,
      });
    },
    getFile: async (id: string) => {
      try {
        const response = await api.get(`/files/${id}`);
        return response;
      } catch (error) {
        if (axios.isAxiosError(error)) {
          console.error('Error fetching file:', error.response?.data?.detail || error.message);
        } else {
          console.error('Error fetching file:', error);
        }
        throw error;
      }
    },
    deleteFile: async (id: string) => {
      return api.delete(`/files/${id}`);
    },

    // --- MODIFIED: Human Input Submission (accepts inputId) --- 
    /**
     * Submit human input for a specific query and tool.
     *
     * @param inputId The unique ID of the specific input request.
     * @param queryId The ID of the query waiting for input.
     * @param toolName The name of the tool that requested input (e.g., __human_input__).
     * @param userInput The text input provided by the user.
     * @returns The response from the backend.
     */
    async submitHumanInput(inputId: string, queryId: string, toolName: string, userInput: string) {
      const url = `/agents/input/${queryId}/${toolName}`; // URL might not need inputId if passed in payload
      // --- MODIFIED: Include input_id in payload --- 
      const payload = { input: userInput, input_id: inputId };
      // --- END MODIFIED ---
      console.log(`[useApi] Submitting human input ${inputId} to ${url}`, payload);
      try {
        const response = await api.post(url, payload);
        console.log('[useApi] Human input submission response:', response.data);
        return response;
      } catch (error) {
        console.error(`[useApi] Error submitting human input ${inputId}:`, error);
        throw error; 
      }
    }
    // --- END MODIFIED ---
  };
};

// Enhanced API hook with retry logic for coordinator status
export const useEnhancedApi = () => {
  // ... rest of file ...
};

// --- ADDED: Export the singleton instance --- 
export default api;
// --- END ADDED ---