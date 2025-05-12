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

const NotFoundPage: React.FC = () => {
  const theme = useTheme();
  const navigate = useNavigate();
  
  // Handle navigation to home
  const handleGoHome = () => {
    navigate('/');
  };

  // Handle reload for navbar
  const handleReload = () => {
    window.location.reload();
  };
  
  return (
    <Box
      className="error-container" // Add a specific class for debugging
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
      {/* Navbar */}
      <LoginNavBar onReload={handleReload} />
      
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
        
        <Typography variant="h4" gutterBottom>
          404
        </Typography>
        
        <Typography variant="h5" gutterBottom>
          Page Not Found
        </Typography>
        
        <Typography variant="body1" color="text.secondary" paragraph sx={{ mt: 2 }}>
          The page you are looking for doesn't exist or has been moved.
        </Typography>
        
        <Button
          variant="contained"
          color="primary"
          size="large"
          onClick={handleGoHome}
          sx={{ mt: 2 }}
        >
          Go to Home
        </Button>
      </Paper>
      </Box>
    </Box>
  );
};

export default NotFoundPage; 