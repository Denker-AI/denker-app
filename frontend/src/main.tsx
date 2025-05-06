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

// Auth0 configuration
const domain = import.meta.env.VITE_AUTH0_DOMAIN || '';
const clientId = import.meta.env.VITE_AUTH0_CLIENT_ID || '';
const audience = import.meta.env.VITE_AUTH0_AUDIENCE || '';

// Check if we're in development mode
const isDev = import.meta.env.DEV || import.meta.env.VITE_NODE_ENV === 'development';

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
          redirect_uri: window.location.origin,
          audience: audience,
        }}
        cacheLocation="localstorage"
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