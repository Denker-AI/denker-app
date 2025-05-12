/**
 * API Service for making HTTP requests to the backend
 */

// Base API URL from environment variables or Electron context
const getApiUrl = () => {
  // Check if in Electron context
  if (window.electron) {
    // Use Electron's environment variables
    return window.electron.getEnvVars().VITE_API_URL;
  }
  // Fallback to Vite env vars or default
  return import.meta.env.VITE_API_URL || 'http://localhost:8001/api/v1';
};

const API_URL = getApiUrl();

// Default headers
const defaultHeaders = {
  'Content-Type': 'application/json',
};

// Helper function to handle API responses
const handleResponse = async (response: Response) => {
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.message || `API Error: ${response.status}`);
  }
  
  // Check if response is empty
  const text = await response.text();
  return text ? JSON.parse(text) : {};
};

// API Service object
export const apiService = {
  /**
   * Make a GET request
   * @param endpoint - API endpoint
   * @param options - Additional fetch options
   * @returns Promise with response data
   */
  async get(endpoint: string, options = {}) {
    const response = await fetch(`${API_URL}${endpoint}`, {
      method: 'GET',
      headers: {
        ...defaultHeaders,
      },
      ...options,
    });
    
    return handleResponse(response);
  },
  
  /**
   * Make a POST request
   * @param endpoint - API endpoint
   * @param data - Request body data
   * @param options - Additional fetch options
   * @returns Promise with response data
   */
  async post(endpoint: string, data: any, options = {}) {
    const response = await fetch(`${API_URL}${endpoint}`, {
      method: 'POST',
      headers: {
        ...defaultHeaders,
      },
      body: JSON.stringify(data),
      ...options,
    });
    
    return handleResponse(response);
  },
  
  /**
   * Make a PUT request
   * @param endpoint - API endpoint
   * @param data - Request body data
   * @param options - Additional fetch options
   * @returns Promise with response data
   */
  async put(endpoint: string, data: any, options = {}) {
    const response = await fetch(`${API_URL}${endpoint}`, {
      method: 'PUT',
      headers: {
        ...defaultHeaders,
      },
      body: JSON.stringify(data),
      ...options,
    });
    
    return handleResponse(response);
  },
  
  /**
   * Make a DELETE request
   * @param endpoint - API endpoint
   * @param options - Additional fetch options
   * @returns Promise with response data
   */
  async delete(endpoint: string, options = {}) {
    const response = await fetch(`${API_URL}${endpoint}`, {
      method: 'DELETE',
      headers: {
        ...defaultHeaders,
      },
      ...options,
    });
    
    return handleResponse(response);
  },
  
  /**
   * Upload a file
   * @param endpoint - API endpoint
   * @param file - File to upload
   * @param additionalData - Additional form data
   * @param options - Additional fetch options
   * @returns Promise with response data
   */
  async uploadFile(endpoint: string, file: File, additionalData = {}, options = {}) {
    const formData = new FormData();
    formData.append('file', file);
    
    // Add any additional data to the form
    Object.entries(additionalData).forEach(([key, value]) => {
      formData.append(key, String(value));
    });
    
    const response = await fetch(`${API_URL}${endpoint}`, {
      method: 'POST',
      body: formData,
      ...options,
    });
    
    return handleResponse(response);
  },
}; 