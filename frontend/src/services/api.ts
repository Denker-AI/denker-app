import { fetchWithAuth } from '../utils/apiClient';
import { getLocalApiUrl, getApiUrl } from './apiService';
const LOCAL_API_URL = getLocalApiUrl();
const API_URL = getApiUrl();

// Helper to handle fetchWithAuth responses
async function handleResponse(response: Response) {
  if (!response.ok) {
    let errorMsg = `API Error: ${response.status}`;
    try {
      const data = await response.json();
      errorMsg = data.message || errorMsg;
    } catch {}
    throw new Error(errorMsg);
  }
  // If no content
  if (response.status === 204) return null;
  return response.json();
}

export const api = {
  // [REMOTE] Cloud backend endpoints
  getConversations: async () => {
    const res = await fetchWithAuth(`/conversations/list`);
    return handleResponse(res);
  },
  createConversation: async (data: any) => {
    const res = await fetchWithAuth(`/conversations/new`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
    return handleResponse(res);
  },
  getConversation: async (id: string, params?: { limit?: number; before_message_id?: string }) => {
    let url = `/conversations/${id}`;
    if (params) {
      const q = new URLSearchParams(params as any).toString();
      url += `?${q}`;
    }
    const res = await fetchWithAuth(url);
    return handleResponse(res);
  },
  updateConversation: async (id: string, data: any) => {
    const res = await fetchWithAuth(`/conversations/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
    return handleResponse(res);
  },
  deleteConversation: async (id: string) => {
    const res = await fetchWithAuth(`/conversations/${id}`, {
      method: 'DELETE',
    });
    return handleResponse(res);
  },
  addMessage: async (conversationId: string, data: any) => {
    const res = await fetchWithAuth(`/conversations/${conversationId}/messages`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
    return handleResponse(res);
  },
  sendMessage: async (text: string, conversationId: string, attachments: any[] = []) => {
    const res = await fetchWithAuth(`/conversations/${conversationId}/messages`, {
      method: 'POST',
      body: JSON.stringify({ content: text, role: 'user', attachments }),
    });
    return handleResponse(res);
  },

  // [LOCAL] Local backend endpoints
  postLocalLogin: async (userInfo: any) => {
    const payload = {
      user_id: userInfo.user_id,
      token: userInfo.token,
    };
    const response = await fetch(`${LOCAL_API_URL}/agents/auth/local-login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      throw new Error('Failed to post user info to local backend');
    }
    return response.json();
  },
  processMCPCoordinator: async (data: any) => {
    const response = await fetch(`${LOCAL_API_URL}/agents/coordinator/mcp-agent`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
      credentials: 'include',
    });
    return handleResponse(response);
  },
  checkCoordinatorStatus: async (queryId: string) => {
    const response = await fetch(`${LOCAL_API_URL}/agents/status/${queryId}`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
    });
    return handleResponse(response);
  },

  // [LOCAL] File endpoints
  uploadFile: async (file: File, additionalData: { user_id?: string | null, query_id?: string, message_id?: string, token?: string | null } = {}) => {
    const formData = new FormData();
    formData.append('file', file);
    // Electron: send the real file path if available
    if ((file as any).path) {
      formData.append('original_path', (file as any).path);
    }
    Object.entries(additionalData).forEach(([key, value]) => {
      if (value !== null && value !== undefined) {
      formData.append(key, String(value));
      }
    });
    const res = await fetch(`${LOCAL_API_URL}/agents/files/process-local`, {
      method: 'POST',
      body: formData,
    });
    return handleResponse(res);
  },
  // [REMOTE] Get files from cloud backend
  getFiles: async (params?: any) => {
    let url = `/files/list`;
    if (params) {
      const q = new URLSearchParams(params as any).toString();
      url += `?${q}`;
    }
    const res = await fetchWithAuth(url);
    return handleResponse(res);
  },
  // Add generic get method for cloud backend
  get: async (endpoint: string) => {
    const res = await fetchWithAuth(endpoint);
    return handleResponse(res);
  },
  // Add generic post method for cloud backend
  post: async (endpoint: string, data: any) => {
    const res = await fetchWithAuth(endpoint, {
      method: 'POST',
      body: JSON.stringify(data),
      // Ensure Content-Type header is set for POST/PUT with JSON body
      headers: {
        'Content-Type': 'application/json',
      },
    });
    return handleResponse(res);
  },
  // Add generic put method for cloud backend
  put: async (endpoint: string, data: any) => {
    const res = await fetchWithAuth(endpoint, {
      method: 'PUT',
      body: JSON.stringify(data),
      // Ensure Content-Type header is set for POST/PUT with JSON body
      headers: {
        'Content-Type': 'application/json',
      },
    });
    return handleResponse(res);
  },
  // Add generic delete method for cloud backend
  delete: async (endpoint: string) => {
    const res = await fetchWithAuth(endpoint, { method: 'DELETE' });
    return handleResponse(res);
  },

  // [LOCAL] New endpoint for refreshing settings, path corrected
  refreshLocalSettings: async () => {
    const response = await fetch(`${LOCAL_API_URL}/settings/refresh-cache`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
    });
    return handleResponse(response); 
  },
  // [LOCAL] Restart coordinator endpoint
  restartCoordinator: async () => {
    const response = await fetch(`${LOCAL_API_URL}/agents/auth/restart-coordinator`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
    });
    return handleResponse(response);
  },
  // [LOCAL] Cancel query endpoint
  cancelQuery: async (queryId: string) => {
    const response = await fetch(`${LOCAL_API_URL}/agents/cancel/${queryId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
    });
    return handleResponse(response);
  },
  // Add more endpoints as needed
};