import React from 'react';
import {
  Box,
  Button,
  Paper,
  Typography,
  useTheme,
  AppBar,
  Toolbar,
  IconButton,
  Alert,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import RefreshIcon from '@mui/icons-material/Refresh';
import EmailIcon from '@mui/icons-material/Email';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';

declare global {
  interface Window {
    electron?: {
      minimizeMainWindow?: () => void;
    };
  }
}

const isElectron = !!(window as any).electron;

const EmailVerificationPage: React.FC = () => {
  const theme = useTheme();

  const handleClose = () => {
    console.log('Close button clicked');
    if (isElectron) {
      (window as any).electron?.minimizeMainWindow?.();
    } else {
      window.close();
    }
  };

  const handleReload = () => {
    console.log('Reload button clicked');
    window.location.reload();
  };

  const handleTryLogin = () => {
    // Navigate back to login
    window.location.href = '/login';
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
      <AppBar 
        position="static" 
        color="default" 
        elevation={1}
        sx={{ 
          WebkitAppRegion: 'drag', 
          userSelect: 'none',
        }}
      >
        <Toolbar variant="dense" sx={{ justifyContent: 'space-between' }}>
          <Box sx={{ 
            WebkitAppRegion: 'no-drag',
            display: 'flex',
            alignItems: 'center',
          }}>
            <IconButton edge="start" color="inherit" aria-label="reload" onClick={handleReload} sx={{ mr: 1 }}>
              <RefreshIcon />
            </IconButton>
            <IconButton edge="start" color="inherit" aria-label="close" onClick={handleClose}>
              <CloseIcon />
            </IconButton>
          </Box>
          <Typography variant="subtitle1" sx={{ 
            position: 'absolute', 
            left: '50%', 
            transform: 'translateX(-50%)', 
            WebkitAppRegion: 'no-drag'
          }}>
            Email Verification Required
          </Typography>
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
            maxWidth: 500,
            width: '100%',
            textAlign: 'center',
          }}
        >
          <EmailIcon 
            sx={{ 
              fontSize: '4rem', 
              color: theme.palette.primary.main, 
              mb: 2 
            }} 
          />
          
          <Typography variant="h5" component="h1" gutterBottom>
            Check Your Email
          </Typography>
          
          <Typography variant="body1" color="text.secondary" sx={{ mb: 3 }}>
            We've sent you a verification email. Please check your inbox and click the verification link to activate your Denker account.
          </Typography>

          <Alert severity="info" sx={{ width: '100%', mb: 3 }}>
            <Typography variant="body2">
              <strong>Don't see the email?</strong> Check your spam folder or wait a few minutes for it to arrive.
            </Typography>
          </Alert>

          <Box sx={{ display: 'flex', gap: 2, flexDirection: 'column', width: '100%' }}>
            <Button
              variant="contained"
              color="primary"
              size="large"
              fullWidth
              onClick={handleTryLogin}
              startIcon={<CheckCircleIcon />}
            >
              I've Verified My Email - Sign In
            </Button>
            
            <Button
              variant="outlined"
              color="primary"
              size="large"
              fullWidth
              onClick={() => window.location.href = '/login'}
            >
              Back to Login
            </Button>
          </Box>
          
          <Typography variant="body2" color="text.secondary" sx={{ mt: 3 }}>
            After verifying your email, return here to sign in and start using Denker!
          </Typography>
        </Paper>
      </Box>
    </Box>
  );
};

export default EmailVerificationPage; 