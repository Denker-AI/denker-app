import React, { useContext, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  Box, 
  Button, 
  Paper, 
  Typography, 
  Alert, 
  AppBar, 
  Toolbar, 
  IconButton, 
  useTheme 
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import RefreshIcon from '@mui/icons-material/Refresh';
import { AuthContext } from '../auth/AuthContext';

declare global {
  interface Window {
    electron?: {
      minimizeMainWindow?: () => void;
    };
  }
}

const isElectron = !!(window as any).electron;

const Login: React.FC = () => {
  const { login, isLoading, error, isFromLogout, isAuthenticated } = useContext(AuthContext);
  const theme = useTheme();
  const navigate = useNavigate();
  const [initialLoad, setInitialLoad] = useState(true);

  useEffect(() => {
    // After 2 seconds, mark initial load as complete
    const timer = setTimeout(() => {
      setInitialLoad(false);
    }, 2000);

    return () => clearTimeout(timer);
  }, []);

  // Redirect to main window if user becomes authenticated
  useEffect(() => {
    if (isAuthenticated && !isLoading) {
      console.log('[Login] User authenticated, redirecting to main window');
      navigate('/', { replace: true });
    }
  }, [isAuthenticated, isLoading, navigate]);

  const handleLogin = () => {
    console.log('Login button clicked');
    login(); // Call the login function from our context
  };

  const handleClose = () => {
    console.log('Close button clicked');
    if (isElectron) {
      // In Electron, minimize might be safer than close, depending on main process setup
      (window as any).electron?.minimizeMainWindow?.(); 
    } else {
      // Standard web behavior (might not be applicable if always in Electron)
      window.close(); 
    }
  };

  const handleReload = () => {
    console.log('Reload button clicked');
    window.location.reload();
  };

  // Determine appropriate messaging based on context
  const getWelcomeMessage = () => {
    if (isFromLogout) {
      return 'Please Sign In';
    }
    return 'Welcome to Denker';
  };

  const getSubMessage = () => {
    if (isFromLogout) {
      return 'Sign in to continue using your AI assistant';
    }
    return 'Your intelligent AI assistant for maximum productivity';
  };

  const getLoadingMessage = () => {
    if (isFromLogout) {
      return {
        primary: 'Signing you back in...',
        secondary: 'Restoring your AI assistant session'
      };
    }
    return {
      primary: initialLoad ? 'Welcome to Denker!' : 'Almost there...',
      secondary: initialLoad 
        ? 'Setting up your AI assistant for maximum productivity' 
        : 'Completing your secure login to get started'
    };
  };

  // Loading state with improved messaging
  if (isLoading || initialLoad) {
    const loadingMessages = getLoadingMessage();
    
    return (
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: '100vh',
          background: `linear-gradient(135deg, ${theme.palette.primary.main}20 0%, ${theme.palette.secondary.main}20 100%)`,
          p: 3
        }}
      >
        <Paper
          elevation={3}
          sx={{
            p: 4,
            borderRadius: 2,
            textAlign: 'center',
            backgroundColor: theme.palette.background.paper,
            backdropFilter: 'blur(10px)',
            minWidth: 300
          }}
        >
          <Typography variant="h6" gutterBottom>
            {loadingMessages.primary}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {loadingMessages.secondary}
          </Typography>
        </Paper>
      </Box>
    );
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
      <AppBar 
        position="static" 
        color="default" 
        elevation={1}
        sx={{ 
          // Make the AppBar draggable, common for frameless Electron windows
          WebkitAppRegion: 'drag', 
          userSelect: 'none', // Prevent text selection on the draggable region
        }}
      >
        <Toolbar variant="dense" sx={{ justifyContent: 'space-between' /* Change alignment */ }}>
          <Box sx={{ 
            // This box will contain buttons, make it non-draggable
            WebkitAppRegion: 'no-drag',
            display: 'flex',
            alignItems: 'center',
            // Removed fixed width spacer
          }}>
            <IconButton edge="start" color="inherit" aria-label="reload" onClick={handleReload} sx={{ mr: 1 }}>
              <RefreshIcon />
            </IconButton>
            <IconButton edge="start" color="inherit" aria-label="close" onClick={handleClose}>
              <CloseIcon />
            </IconButton>
          </Box>
          <Typography variant="subtitle1" sx={{ position: 'absolute', left: '50%', transform: 'translateX(-50%)', WebkitAppRegion: 'no-drag' /* Title text itself should not drag */ }}>
            Denker Login
          </Typography>
          {/* Empty Box to balance the toolbar for space-between */}
          <Box /> 
        </Toolbar>
      </AppBar>
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          bgcolor: theme.palette.background.default,
          p: 3,
        }}
      >
        <Paper
          elevation={3}
          sx={{
            p: 4,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            maxWidth: 400,
            width: '100%',
          }}
        >
          <Typography variant="h5" component="h1" gutterBottom align="center">
            {getWelcomeMessage()}
          </Typography>
          
          {/* Show subtitle only for new users */}
          {!isFromLogout && (
            <Typography variant="body1" color="text.secondary" sx={{ mb: 2, textAlign: 'center' }}>
              {getSubMessage()}
            </Typography>
          )}
          
          {error && (
            <Alert severity="error" sx={{ width: '100%', mb: 2 }}>
              Login Failed: {error}
            </Alert>
          )}
          
          <Box sx={{ mt: 2, width: '100%', textAlign: 'center' }}>
            {isLoading ? (
              <>
                <Typography variant="body2" color="text.secondary">
                  {error ? 'Retrying...' : 'Processing Login...'} 
                </Typography>
              </>
            ) : (
              <Button
                variant="contained"
                color="primary"
                size="large"
                fullWidth
                onClick={handleLogin}
                disabled={isLoading}
              >
                {isFromLogout ? 'Sign In' : 'Log In / Sign Up'}
              </Button>
            )}
          </Box>
          
          {!isLoading && (
            <Typography variant="body2" color="text.secondary" sx={{ mt: 3, textAlign: 'center' }}>
              {isFromLogout 
                ? 'Click to sign back in securely via your browser.'
                : 'Click the button to securely log in or sign up via your browser. New users will need to verify their email address.'
              }
            </Typography>
          )}
          
        </Paper>
      </Box>
    </Box>
  );
};

export default Login; 