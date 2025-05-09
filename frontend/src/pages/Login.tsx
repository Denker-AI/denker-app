import React from 'react';
import { useAuth0 } from '@auth0/auth0-react';
import { Navigate } from 'react-router-dom';
import {
  Box,
  Button,
  Typography,
  Container,
  Paper,
  useTheme,
} from '@mui/material';
import LockOutlinedIcon from '@mui/icons-material/LockOutlined';
import LoginNavBar from '../components/Auth/LoginNavBar';

const Login: React.FC = () => {
  const { isAuthenticated, loginWithRedirect, isLoading } = useAuth0();
  const theme = useTheme();

  // Redirect if already authenticated
  if (isAuthenticated && !isLoading) {
    return <Navigate to="/" replace />;
  }

  // Handle retry login
  const handleRetryLogin = () => {
    loginWithRedirect();
  };

  return (
    <Box 
      className="login-container" // Add a specific class for debugging
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
        zIndex: 9999, // Ensure it appears above other content
      }}
    >
      {/* Login navbar */}
      <LoginNavBar onReload={handleRetryLogin} />
      
      {/* Login content */}
      <Container component="main" maxWidth="xs" sx={{ 
        flexGrow: 1, 
        display: 'flex', 
        alignItems: 'center',
        justifyContent: 'center',
        py: 3,
      }}>
        <Paper
          elevation={3}
          className="glass"
          sx={{
            p: 4,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            width: '100%',
            backgroundColor: 'rgba(30, 30, 30, 0.6)',
            backdropFilter: 'blur(10px)',
            borderRadius: 2,
          }}
        >
          <Box
            sx={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              mb: 3,
            }}
          >
            <Box
              sx={{
                bgcolor: 'primary.main',
                borderRadius: '50%',
                p: 1,
                mb: 2,
                display: 'flex',
                justifyContent: 'center',
                alignItems: 'center',
              }}
            >
              <LockOutlinedIcon fontSize="large" />
            </Box>
            <Typography component="h1" variant="h5">
              Welcome to Denker AI
            </Typography>
            <Typography variant="body2" color="text.secondary" align="center" sx={{ mt: 1 }}>
              Your AI-powered Knowledge Partner
            </Typography>
          </Box>

          <Button
            fullWidth
            variant="contained"
            color="primary"
            size="large"
            onClick={() => loginWithRedirect()}
            sx={{ mt: 2, mb: 2 }}
            className="non-draggable"
            disabled={isLoading}
          >
            {isLoading ? 'Signing In...' : 'Sign In'}
          </Button>
          
          <Typography variant="body2" color="text.secondary" align="center">
            Powered by Auth0
          </Typography>
        </Paper>
      </Container>
    </Box>
  );
};

export default Login; 