import React from 'react';
import ReactDOM from 'react-dom/client';
import { HashRouter } from 'react-router-dom';
import { Auth0Provider } from '@auth0/auth0-react';
import { ThemeProvider, CssBaseline } from '@mui/material';
import App from './App';
import theme from './theme';
import './index.css';
import initBrowserActionHandler from './utils/browserActionHandler';

// Initialize global handlers
initBrowserActionHandler();

// Global error handling
window.addEventListener('error', (event) => {
  console.error('GLOBAL ERROR:', event.error);
  
  // Check if it's Auth0 related
  if (event.error?.message?.includes('auth0') || 
      event.error?.stack?.includes('auth0') ||
      event.filename?.includes('auth0')) {
    console.error('Auth0 related error detected:', event);
    
    // Try to redirect to our error page
    try {
      const isElectron = window.electron !== undefined;
      if (isElectron && window.electron) {
        window.location.href = '#/auth/error';
      } else {
        const errorMessage = encodeURIComponent(event.error?.message || 'Unknown Auth0 error');
        window.location.href = `#/auth/error?error=global_auth0_error&error_description=${errorMessage}`;
      }
    } catch (e) {
      console.error('Failed to redirect to error page:', e);
    }
  }
});

// Check if running in Electron
const isElectron = window.electron !== undefined;

// Listen for Auth0 callback events from Electron main process
if (isElectron && window.electron) {
  // Listen for auth0-callback events from the main process via the preload script
  window.electron.onAuth0Callback((hashRoute: string) => {
    console.log('Auth0 callback received from Electron main process:', hashRoute);
    window.location.hash = hashRoute;
  });
  
  // Also listen for custom events dispatched by the preload script
  document.addEventListener('auth0-callback-received', (event: any) => {
    console.log('Auth0 callback received via custom event:', event.detail);
    window.location.hash = event.detail;
  });
}

// Auth0 configuration - get from Electron if available, otherwise use Vite env vars
let domain, clientId, audience;

// Helper function to clear Auth0 cache from localStorage
const clearAuth0Cache = () => {
  // This helps when switching accounts
  console.log('Clearing Auth0 cache from localStorage');
  
  // Find and remove Auth0-related items
  const keysToRemove = [];
  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i);
    if (key && (
      key.startsWith('auth0') || 
      key.includes('auth0') || 
      key.startsWith('@@auth0') ||
      key.includes('user-info') ||
      key.includes('denker-user')
    )) {
      keysToRemove.push(key);
    }
  }
  
  // Remove all keys in a separate loop to avoid iteration issues
  keysToRemove.forEach(key => {
    console.log('Removing cached Auth0 key:', key);
    localStorage.removeItem(key);
  });
};

if (isElectron && window.electron) {
  // Get environment variables from Electron
  const electronEnv = (window.electron as any).getEnvVars();
  domain = electronEnv.VITE_AUTH0_DOMAIN || 'auth.denker.ai';
  clientId = electronEnv.VITE_AUTH0_CLIENT_ID || 'lq6uzeeUp9i14E8FNpJwr0DVIP5VtOzQ';
  audience = electronEnv.VITE_AUTH0_AUDIENCE || 'https://api.denker.ai';
  
  console.log('🔐 Auth0 config loaded from Electron:', {
    domain: domain,
    clientId: clientId ? (clientId.slice(0, 8) + '...') : 'MISSING',
    audience: audience || 'MISSING'
  });
  
  // Check for auth failure or token expiration in URL
  const url = new URL(window.location.href);
  const errorParam = url.searchParams.get('error');
  if (errorParam) {
    console.log('Auth error detected in URL, clearing cache');
    clearAuth0Cache();
  }
} else {
  // Regular browser - use Vite env vars
  domain = import.meta.env.VITE_AUTH0_DOMAIN || 'auth.denker.ai';
  clientId = import.meta.env.VITE_AUTH0_CLIENT_ID || 'lq6uzeeUp9i14E8FNpJwr0DVIP5VtOzQ';
  audience = import.meta.env.VITE_AUTH0_AUDIENCE || 'https://api.denker.ai';
}

// Force settings in development mode
const isDev = import.meta.env.DEV === true || import.meta.env.VITE_NODE_ENV === 'development'; 

// In development mode, use fixed URLs
const redirectUri = isDev 
  ? 'http://localhost:5173/callback'
  : (isElectron ? 'denker://callback' : window.location.origin + '/callback');

// For Electron, we need to handle custom protocol
if (isElectron) {
  // For Electron in development mode using localhost
  if (isDev) {
    console.log('Using development redirect URI for Auth0:', redirectUri);
  } 
  // For packaged Electron app, we need to use the custom protocol
  else {
    // Ensure we're using the custom protocol in production
    const customProtocolUrl = 'denker://callback';
    console.log('Using custom protocol redirect URI for Auth0:', customProtocolUrl);
  }
}

// Log config for debugging
console.log('Auth0 Configuration:', {
  domain,
  clientId: clientId ? (clientId.slice(0, 8) + '...') : 'MISSING',
  audience: audience || 'MISSING',
  redirectUri,
  isDev,
  isElectron,
  fullOrigin: window.location.origin,
});

// Error handler for Auth0
const onRedirectCallback = (appState: any) => {
  console.log('Auth0 redirect callback', appState);
  
  // Navigate to the intended route (or home if none provided)
  const targetUrl = appState?.returnTo || window.location.pathname || '/';
  
  // In Electron environment, handle differently
  if (isElectron && window.electron) {
    window.location.href = `#${targetUrl}`;
  } else {
    // For web, use regular path
    window.location.pathname = targetUrl;
  }
};

// Define error handler (for use with window.addEventListener)
const onError = (error: Error) => {
  console.error('Auth0 error:', error);
  console.error('Auth0 error details:', {
    name: error.name,
    message: error.message,
    stack: error.stack,
  });
  
  // Force console to be visible
  console.log('%c AUTH0 ERROR - Check above for details', 'background: #ff0000; color: white; font-size: 20px');
  
  // Redirect to our custom error page
  if (isElectron && window.electron) {
    console.log('Redirecting to error page in Electron');
    
    // Use setTimeout to ensure logs are displayed
    setTimeout(() => {
      window.location.href = '#/auth/error';
    }, 500);
  } else {
    // For web, include the error information in the URL
    const errorMessage = encodeURIComponent(error.message || 'Unknown error');
    console.log(`Redirecting to error page in browser with message: ${errorMessage}`);
    
    // Use setTimeout to ensure logs are displayed
    setTimeout(() => {
      window.location.href = `#/auth/error?error=auth0_error&error_description=${errorMessage}`;
    }, 500);
  }
};

// Render the app
const root = ReactDOM.createRoot(document.getElementById('root')!);

// In development mode with missing Auth0 credentials, render without Auth0Provider
if (isDev && (!domain || !clientId)) {
  root.render(
    <React.StrictMode>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <HashRouter>
          <App />
        </HashRouter>
      </ThemeProvider>
    </React.StrictMode>
  );
} else {
  // Normal rendering with Auth0Provider
  root.render(
    <React.StrictMode>
      <Auth0Provider
        domain={domain}
        clientId={clientId}
        authorizationParams={{
          redirect_uri: isElectron && !isDev ? 'denker://callback' : redirectUri,
          audience: audience,
          scope: 'openid profile email',
        }}
        useRefreshTokens={true}
        cacheLocation="localstorage"
        onRedirectCallback={onRedirectCallback}
      >
        <ThemeProvider theme={theme}>
          <CssBaseline />
          <HashRouter>
            <App />
          </HashRouter>
        </ThemeProvider>
      </Auth0Provider>
    </React.StrictMode>
  );
} 