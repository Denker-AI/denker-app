import React from 'react';
import {
  Box,
  Typography,
  Button,
  Paper,
  useTheme,
} from '@mui/material';
import { useNavigate } from 'react-router-dom';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import LoginNavBar from '../components/Auth/LoginNavBar';
import { useAuth0 } from '@auth0/auth0-react';

const UnauthorizedPage: React.FC = () => {
  const theme = useTheme();
  const navigate = useNavigate();
  const { loginWithRedirect } = useAuth0();
  
  // Handle retry login
  const handleRetryLogin = () => {
    loginWithRedirect({
      // Add additional params if needed
      appState: { 
        returnTo: '/' 
      }
    });
  };

  // Handle navigation to home
  const handleGoHome = () => {
    navigate('/');
  };
  
  return (
    <Box 
      className="unauthorized-container"
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
      {/* Login navbar */}
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
            Authentication Issue
          </Typography>
          
          <Typography variant="body1" color="text.secondary" paragraph sx={{ mt: 2 }}>
            There was a problem with your authentication. This could be due to session expiration or invalid credentials.
          </Typography>
          
          <Box sx={{ mt: 3, display: 'flex', flexDirection: 'column', gap: 2 }}>
            <Button
              fullWidth
              variant="contained"
              color="primary"
              size="large"
              onClick={handleRetryLogin}
            >
              Sign In Again
            </Button>
            
            <Button
              fullWidth
              variant="outlined"
              color="primary"
              size="large"
              onClick={handleGoHome}
            >
              Go to Home
            </Button>
          </Box>
        </Paper>
      </Box>
    </Box>
  );
};

export default UnauthorizedPage; 