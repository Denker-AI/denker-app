import { fetchWithAuth } from '../utils/apiClient';

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
  // Conversations
  getConversations: async () => {
    const res = await fetchWithAuth('/conversations/list');
    return handleResponse(res);
  },
  createConversation: async (data: any) => {
    const res = await fetchWithAuth('/conversations/new', {
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
  // Coordinator endpoints
  processMCPCoordinator: async (data: any) => {
    const res = await fetchWithAuth('/agents/coordinator/mcp-agent', {
      method: 'POST',
      body: JSON.stringify(data),
    });
    return handleResponse(res);
  },
  checkCoordinatorStatus: async (queryId: string) => {
    const res = await fetchWithAuth(`/agents/status/${queryId}`);
    return handleResponse(res);
  },
  // File endpoints
  uploadFile: async (file: File, additionalData = {}) => {
    const formData = new FormData();
    formData.append('file', file);
    Object.entries(additionalData).forEach(([key, value]) => {
      formData.append(key, String(value));
    });
    const res = await fetchWithAuth('/files/upload', {
      method: 'POST',
      body: formData,
    });
    return handleResponse(res);
  },
  getFiles: async (params?: any) => {
    let url = '/files/list';
    if (params) {
      const q = new URLSearchParams(params as any).toString();
      url += `?${q}`;
    }
    const res = await fetchWithAuth(url);
    return handleResponse(res);
  },
  // Add more endpoints as needed
};