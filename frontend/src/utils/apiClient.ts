const API_BASE_URL = window.electron?.getEnvVars()?.VITE_API_URL || 'http://localhost:8001/api/v1';

/**
 * Fetches data from the backend API, automatically handling authentication.
 * 
 * @param endpoint The API endpoint (e.g., '/chats')
 * @param options Standard Fetch API options (method, headers, body, etc.)
 * @returns Promise<Response> The Fetch API Response object
 * @throws Error if authentication token cannot be retrieved or fetch fails
 */
export const fetchWithAuth = async (
  endpoint: string, 
  options: RequestInit = {}
): Promise<Response> => {
  let token: string | null = null;
  
  try {
    // 1. Request token from main process via IPC
    token = await window.electron?.getAccessToken();
  } catch (error) {
    console.error('Error requesting access token via IPC:', error);
    // Decide how to handle this - maybe throw a specific error?
    // For now, we proceed without a token, the API might return 401.
  }
  
  // 2. Prepare headers
  const headers = new Headers(options.headers || {});
  headers.set('Content-Type', headers.get('Content-Type') || 'application/json');
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  } else {
    console.warn('fetchWithAuth: No access token available for request to', endpoint);
    // If no token, depending on the API, this request might fail (e.g., 401 Unauthorized)
  }
  
  // 3. Construct full URL
  const url = `${API_BASE_URL}${endpoint}`;
  
  // 4. Make the fetch request
  console.log(`fetchWithAuth: ${options.method || 'GET'} ${url}`);
  const response = await fetch(url, {
    ...options,
    headers,
  });
  
  // 5. Optional: Check for 401 Unauthorized response - might indicate expired token
  if (response.status === 401) {
    console.error('fetchWithAuth: Received 401 Unauthorized. Token might be invalid or expired.');
    // Here you could potentially trigger a logout or token refresh attempt
    // For now, just let the caller handle the 401.
  }
  
  return response;
};

// Example usage (replace existing fetch calls with this):
/*
async function getMyChats() {
  try {
    const response = await fetchWithAuth('/chats');
    if (!response.ok) {
      throw new Error(`API Error: ${response.statusText}`);
    }
    const data = await response.json();
    console.log('Chats:', data);
  } catch (error) {
    console.error('Failed to fetch chats:', error);
  }
}
*/

// If you use Axios, you would create an Axios instance and an interceptor:
/*
import axios from 'axios';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
});

apiClient.interceptors.request.use(async (config) => {
  try {
    const token = await window.electron?.getAccessToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  } catch (error) {
    console.error('Error getting access token for Axios request:', error);
  }
  return config;
}, (error) => {
  return Promise.reject(error);
});

export default apiClient;
*/ 