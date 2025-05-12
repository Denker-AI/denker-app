import React from 'react';
import ReactDOM from 'react-dom/client';
import { HashRouter } from 'react-router-dom';
import { ThemeProvider, CssBaseline } from '@mui/material';
import App from './App';
import theme from './theme';
import './index.css';
import initBrowserActionHandler from './utils/browserActionHandler';
import { AuthProvider } from './auth/AuthContext';

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

console.log('🚀 Renderer process started. Timestamp:', Date.now());
console.log('  Initial window.electron type:', typeof window.electron);
// Check for the flag set by preload.js. `window as any` is used because the property is dynamically added.
console.log('  Initial window.electronIsPreloadedByScript:', (window as any).electronIsPreloadedByScript);

// This setTimeout is for debugging to see if properties appear later.
setTimeout(() => {
  console.log('⏰ After 200ms delay in main.tsx:');
  console.log('  Delayed window.electron type:', typeof window.electron);
  console.log('  Delayed window.electronIsPreloadedByScript:', (window as any).electronIsPreloadedByScript);
}, 200);

// Determine if running in Electron. Order of checks: direct API, preload flag, user agent.
const electronAPIDetected = typeof window.electron !== 'undefined';
const preloadScriptFlag = (window as any).electronIsPreloadedByScript === true;
const userAgentIndicatesElectron = navigator.userAgent.toLowerCase().includes('electron/');

const isElectron = electronAPIDetected || preloadScriptFlag || userAgentIndicatesElectron;

console.log('🔧 Final isElectron determination:', isElectron, {
  electronAPIDetected,
  preloadScriptFlag,
  userAgentIndicatesElectron
});

// Determine if dev mode
const isDev = import.meta.env.DEV === true || 
  import.meta.env.VITE_NODE_ENV === 'development' || 
  (isElectron && window.electron && window.electron.getEnvVars()?.VITE_NODE_ENV === 'development');

const rootElement = document.getElementById('root');
if (!rootElement) {
  throw new Error("Failed to find the root element with id 'root'");
}
const root = ReactDOM.createRoot(rootElement);

// Get environment variables once from preload
const envVars = window.electron?.getEnvVars() || {};
console.log('🔑 Renderer received ENV VARS from preload:', envVars);

// Potentially pass envVars down via context if needed elsewhere

// Render the app wrapped with AuthProvider
root.render(
  <React.StrictMode>
    <AuthProvider>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <HashRouter>
          <App />
        </HashRouter>
      </ThemeProvider>
    </AuthProvider>
  </React.StrictMode>
);

// Call initBrowserActionHandler if it's still needed
if (typeof initBrowserActionHandler === 'function') {
  initBrowserActionHandler();
} 