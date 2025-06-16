import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext'; // Import the custom hook
import {
  Box,
  Button,
  CircularProgress,
  Typography,
  Paper,
  Alert,
  AppBar,
  Toolbar,
  IconButton,
} from '@mui/material';
import { useTheme } from '@mui/material/styles';
import CloseIcon from '@mui/icons-material/Close';
import RefreshIcon from '@mui/icons-material/Refresh';

// No need to redefine the Window interface - we'll use type assertions instead

// Check if running in Electron
const isElectron = window.navigator.userAgent.toLowerCase().indexOf('electron') > -1;

const Login: React.FC = () => {
  // Use our custom hook instead of useAuth0
  const { login, isLoading, isAuthenticated, error } = useAuth();
  const navigate = useNavigate();
  const theme = useTheme();
  
  // Track if this is initial loading vs actual login loading
  const [initialLoad, setInitialLoad] = React.useState(true);
  
  // Redirect if already authenticated
  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      console.log('[Login Page] Already authenticated, redirecting to /');
      navigate('/'); // Navigate to the main app route
    }
  }, [isLoading, isAuthenticated, navigate]);

  // Set initial load to false after a short delay
  useEffect(() => {
    const timer = setTimeout(() => {
      setInitialLoad(false);
    }, 2000); // Give 2 seconds for initial auth check
    
    return () => clearTimeout(timer);
  }, []);

  const handleLogin = () => {
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

  // Loading state with improved messaging
  if (isLoading || initialLoad) {
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
          <CircularProgress size={60} sx={{ mb: 3, color: theme.palette.primary.main }} />
          <Typography variant="h6" gutterBottom>
            {initialLoad ? 'Welcome to Denker!' : 'Almost there...'}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {initialLoad 
              ? 'Setting up your AI assistant for maximum productivity' 
              : 'Completing your secure login to get started'
            }
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
            Welcome to Denker
          </Typography>
          
          {error && (
            <Alert severity="error" sx={{ width: '100%', mb: 2 }}>
              Login Failed: {error}
            </Alert>
          )}
          
          <Box sx={{ mt: 2, width: '100%', textAlign: 'center' }}>
            {isLoading ? (
              <>
                <CircularProgress sx={{ mb: 1 }}/>
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
                Log In / Sign Up
              </Button>
            )}
          </Box>
          
          {!isLoading && (
            <Typography variant="body2" color="text.secondary" sx={{ mt: 3, textAlign: 'center' }}>
              Click the button to securely log in or sign up via your browser.
            </Typography>
          )}
          
        </Paper>
      </Box>
    </Box>
  );
};

export default Login; 