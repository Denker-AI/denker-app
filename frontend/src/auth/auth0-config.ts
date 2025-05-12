// Force settings in development mode
const isDev = import.meta.env.DEV === true || import.meta.env.VITE_NODE_ENV === 'development'; 
const isElectron = window.navigator.userAgent.toLowerCase().indexOf('electron') > -1;

// Check for completed authentication by system browser
const checkSystemBrowserAuth = () => {
  try {
    const authCompleted = localStorage.getItem('denker_auth_completed');
    if (authCompleted === 'true') {
      console.log('🔑 System browser auth detected from localStorage');
      // Clear the flag to avoid repeated processing
      localStorage.removeItem('denker_auth_completed');
      return true;
    }
  } catch (e) {
    console.warn('Error checking localStorage:', e);
  }
  return false;
};

// Handle the system browser authentication completion
if (isElectron && checkSystemBrowserAuth()) {
  console.log('🔓 System browser auth detected, forcing app to home page');
  window.location.hash = '/';
  // Create a custom event to signal authentication is complete
  try {
    const event = new CustomEvent('denker-auth-complete');
    document.dispatchEvent(event);
  } catch (e) {
    console.error('Error dispatching auth event:', e);
  }
}

// Keep constants if they are used elsewhere, otherwise remove
const auth0Domain = import.meta.env.VITE_AUTH0_DOMAIN || 'auth.denker.ai';
const auth0ClientId = import.meta.env.VITE_AUTH0_CLIENT_ID || 'lq6uzeeUp9i14E8FNpJwr0DVIP5VtOzQ';
const auth0Audience = import.meta.env.VITE_AUTH0_AUDIENCE || 'https://api.denker.ai';

// Export only necessary constants, or remove entirely if not needed by renderer
export const auth0Config = {
  domain: auth0Domain,
  clientId: auth0ClientId,
  audience: auth0Audience,
  // Remove properties related to Auth0Provider config if no longer needed
  // redirectUri: getRedirectUri(), // Handled by main process
  // logoutUri: ... , // Handled by main process
  // cacheLocation: 'localstorage' as const, // SDK config, not needed directly
  // useRefreshTokens: true, // SDK config, not needed directly
  // authorizationParams: { ... }, // SDK config, not needed directly
  // onRedirectCallback: onRedirectCallback, // Handled by IPC
};

// Log configuration only if needed for debugging renderer-side constants
console.log('🔐 Auth0 Configuration Constants (Renderer):', {
  domain: auth0Config.domain,
  clientId: auth0Config.clientId.substring(0, 8) + '...',
  audience: auth0Config.audience,
  isElectron, // Keep these flags if used by renderer logic
  isDev
});