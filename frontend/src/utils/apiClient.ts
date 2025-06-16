import { getCachedAccessToken } from './token-cache';

let API_BASE_URL;
if (import.meta.env.DEV) {
  API_BASE_URL = 'http://localhost:8001/api/v1';
} else {
  // IMPORTANT: Replace this with your actual production API URL
  API_BASE_URL = import.meta.env.VITE_API_URL_PROD || 'https://your-prod-api.denker.ai/api/v1'; 
}
console.log('[fetchWithAuth] Determined API_BASE_URL:', API_BASE_URL, '(Dev mode:', import.meta.env.DEV+')');

// Define ElectronAPI interface for TypeScript
interface ElectronAPI {
  getAccessToken?: () => Promise<string>;
  getUserInfo?: () => Promise<any>;
  getApiUrl?: () => Promise<string>;
  getApiKey?: () => Promise<string>;
  getEnvVars?: () => Record<string, string>;
  onSelectedOption?: (callback: (option: any) => void) => void;
  [key: string]: any;
}

// Instead of extending Window interface directly, use type assertion when needed
// This avoids conflicts with other declarations

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
  console.log('[fetchWithAuth] called with endpoint:', endpoint, 'options:', options);
  let token: string | null = null;
  
  try {
    // Use cached token system to prevent multiple simultaneous getAccessToken calls
    token = await getCachedAccessToken();
    console.log('[fetchWithAuth] Token:', token ? 'Found token' : 'No token');
  } catch (error) {
    console.error('Error requesting access token via cached system:', error);
    // For development, don't crash on missing Electron APIs
    if (import.meta.env.DEV) {
      console.log('[fetchWithAuth] Using dev fallback token');
      token = 'dev-mode-token';
    }
  }
  
  // 2. Prepare headers
  const headers = new Headers(options.headers || {});
  // headers.set('Content-Type', headers.get('Content-Type') || 'application/json');

  // Only set default Content-Type if it's not FormData and not already set
  if (!(options.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  // If it is FormData, we let fetch() set the Content-Type header automatically.
  // If options.headers already contains a Content-Type for FormData, fetch() will use that,
  // but this is generally not recommended as fetch handles the boundary parameter best.

  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  } else {
    console.warn('fetchWithAuth: No access token available for request to', endpoint);
    // If no token, depending on the API, this request might fail (e.g., 401 Unauthorized)
  }
  
  // 3. Construct full URL
  const url = `${API_BASE_URL}${endpoint}`;
  console.log('[fetchWithAuth] Final URL:', url, 'Headers:', headers);
  
  // 4. Make the fetch request
  console.log(`fetchWithAuth: ${options.method || 'GET'} ${url}`);
  const response = await fetch(url, {
    ...options,
    headers,
    credentials: 'include', // Include cookies in the request
  });
  console.log('[fetchWithAuth] Response status:', response.status);
  
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