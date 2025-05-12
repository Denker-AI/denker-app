import React, { useEffect, useState } from 'react';
import {
  Box,
  Typography,
  Button,
  Paper,
  useTheme,
} from '@mui/material';
import { useNavigate, useLocation } from 'react-router-dom';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import LoginNavBar from '../components/Auth/LoginNavBar';

const AuthErrorPage: React.FC = () => {
  const theme = useTheme();
  const navigate = useNavigate();
  const location = useLocation();
  const [errorMessage, setErrorMessage] = useState<string>('Authentication failed');
  
  // Extract error info from URL parameters
  useEffect(() => {
    const searchParams = new URLSearchParams(location.search);
    const error = searchParams.get('error');
    const errorDescription = searchParams.get('error_description');
    
    if (error) {
      setErrorMessage(error);
    }
    
    if (errorDescription) {
      setErrorMessage(`${error || 'Authentication error'}: ${errorDescription}`);
    }
    
    // Advanced debugging
    const debugInfo = {
      error,
      errorDescription,
      url: window.location.href,
      domain: import.meta.env.VITE_AUTH0_DOMAIN,
      clientId: import.meta.env.VITE_AUTH0_CLIENT_ID?.substring(0, 8) + '...',
      audience: import.meta.env.VITE_AUTH0_AUDIENCE,
      isDev: import.meta.env.DEV,
      isElectron: window.electron !== undefined,
      origin: window.location.origin,
      path: window.location.pathname,
      hash: window.location.hash,
      search: window.location.search,
    };
    
    // Log for debugging
    console.error('Auth error debug info:', debugInfo);
  }, [location]);
  
  // Handle navigation to login
  const handleRetryLogin = () => {
    // Navigate back to login page
    navigate('/login');
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
        position: 'absolute',
        top: 0,
        left: 0,
        zIndex: 9999,
      }}
    >
      {/* Navbar */}
      <LoginNavBar onReload={handleRetryLogin} />
      
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
            Authentication Error
          </Typography>
          
          <Typography variant="body1" color="text.secondary" paragraph sx={{ mt: 2 }}>
            {errorMessage}
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

export default AuthErrorPage; 