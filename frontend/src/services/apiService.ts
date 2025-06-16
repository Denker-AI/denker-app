/**
 * API Service for making HTTP requests to the backend
 */

// Base API URL from environment variables or Electron context (CLOUD BACKEND)
export const getApiUrl = () => {
  if (window.electron) {
    // Prefer production variable if set
    return (
      window.electron.getEnvVars().VITE_API_URL_PROD ||
      window.electron.getEnvVars().VITE_API_URL ||
      'http://localhost:8001/api/v1'
    );
  }
  // Prefer production variable if set
  return (
    import.meta.env.VITE_API_URL_PROD ||
    import.meta.env.VITE_API_URL ||
    'http://localhost:8001/api/v1'
  );
};

const API_URL = getApiUrl();

// Local backend API URL (for MCP agent endpoints)
export const getLocalApiUrl = () => {
  let resultUrl: string;
  if (window.electron) {
    const envVars = window.electron.getEnvVars();
    const localApiUrl = envVars?.VITE_LOCAL_API_URL;
    resultUrl = localApiUrl || 'http://localhost:9001/api/v1';
    console.log(`[apiService] Electron: Using local API URL: ${resultUrl}`); // Log the chosen URL
  } else {
    const localApiUrl = import.meta.env.VITE_LOCAL_API_URL;
    resultUrl = localApiUrl || 'http://localhost:9001/api/v1';
    console.log(`[apiService] Non-Electron: Using local API URL: ${resultUrl}`); // Log the chosen URL
  }
  return resultUrl;
};
const LOCAL_API_URL = getLocalApiUrl();

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
    // Electron: send the real file path if available
    if ((file as any).path) {
      formData.append('original_path', (file as any).path);
    }
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