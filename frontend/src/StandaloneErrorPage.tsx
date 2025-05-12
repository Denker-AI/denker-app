import React, { useEffect, useState } from 'react';
import ReactDOM from 'react-dom/client';
import {
  Box,
  Typography,
  Button,
  Paper,
  ThemeProvider,
  CssBaseline,
} from '@mui/material';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import theme from './theme';

// Standalone error page that can be loaded directly without the App component
const StandaloneErrorPage: React.FC = () => {
  const [errorDetails, setErrorDetails] = useState({
    error: 'Authentication Error',
    errorDescription: 'An unknown error occurred during authentication.',
    origin: '',
    path: '',
    hash: '',
    search: '',
  });
  
  // Extract error info from URL parameters
  useEffect(() => {
    // Get URL search params from hash or regular search
    const hash = window.location.hash.replace('#', '');
    const searchParams = new URLSearchParams(window.location.search || hash);
    
    const error = searchParams.get('error');
    const errorDescription = searchParams.get('error_description');
    
    setErrorDetails({
      error: error || 'Authentication Error',
      errorDescription: errorDescription || 'An unknown error occurred during authentication.',
      origin: window.location.origin,
      path: window.location.pathname,
      hash: window.location.hash,
      search: window.location.search,
    });
    
    // Log for debugging
    console.error('Auth error debug info:', {
      error,
      errorDescription,
      url: window.location.href,
      origin: window.location.origin,
      path: window.location.pathname,
      hash: window.location.hash,
      search: window.location.search,
    });
  }, []);
  
  // Handle retry login
  const handleRetryLogin = () => {
    // Redirect to login page or home
    window.location.href = '/';
  };
  
  return (
    <Box 
      className="auth-error-container"
      sx={{ 
        display: 'flex', 
        flexDirection: 'column', 
        height: '100vh', 
        width: '100%',
        margin: 0,
        padding: 0,
        overflow: 'hidden',
        backgroundColor: theme.palette.background.default,
      }}
    >
      {/* Simple navbar */}
      <Box
        sx={{
          height: 48,
          backgroundColor: 'rgba(18, 18, 18, 0.8)',
          borderBottom: '1px solid rgba(255, 255, 255, 0.1)',
          backdropFilter: 'blur(10px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '0 16px',
        }}
      >
        <Typography
          variant="subtitle1"
          component="div"
          sx={{ 
            fontWeight: 500,
            color: 'error.main',
            textAlign: 'center',
          }}
        >
          Authentication Error
        </Typography>
      </Box>
      
      {/* Content */}
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          alignItems: 'center',
          flexGrow: 1,
          width: '100%',
          p: 3,
        }}
      >
        <Paper
          elevation={0}
          sx={{
            p: 4,
            backgroundColor: 'rgba(30, 30, 30, 0.6)',
            backdropFilter: 'blur(10px)',
            border: '1px solid rgba(255, 255, 255, 0.1)',
            borderRadius: 2,
            maxWidth: 500,
            width: '100%',
            textAlign: 'center',
          }}
        >
          <ErrorOutlineIcon sx={{ fontSize: 80, color: 'error.main', mb: 2 }} />
          
          <Typography variant="h5" gutterBottom>
            {errorDetails.error}
          </Typography>
          
          <Typography variant="body1" color="text.secondary" paragraph sx={{ mt: 2 }}>
            {errorDetails.errorDescription}
          </Typography>
          
          <Button
            variant="contained"
            color="primary"
            size="large"
            onClick={handleRetryLogin}
            sx={{ mt: 2 }}
          >
            Try Again
          </Button>
        </Paper>
      </Box>
    </Box>
  );
};

// Initialize if this script is loaded standalone
if (document.getElementById('standalone-error-root')) {
  const root = ReactDOM.createRoot(document.getElementById('standalone-error-root')!);
  root.render(
    <React.StrictMode>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <StandaloneErrorPage />
      </ThemeProvider>
    </React.StrictMode>
  );
}

export default StandaloneErrorPage; 