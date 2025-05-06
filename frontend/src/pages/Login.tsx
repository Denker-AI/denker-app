import React from 'react';
import { useAuth0 } from '@auth0/auth0-react';
import { Navigate } from 'react-router-dom';
import {
  Box,
  Button,
  Typography,
  Container,
  Paper,
} from '@mui/material';
import LockOutlinedIcon from '@mui/icons-material/LockOutlined';

const Login: React.FC = () => {
  const { isAuthenticated, loginWithRedirect, isLoading } = useAuth0();

  // Redirect if already authenticated
  if (isAuthenticated && !isLoading) {
    return <Navigate to="/" replace />;
  }

  return (
    <Container component="main" maxWidth="xs" sx={{ height: '100vh', display: 'flex', alignItems: 'center' }}>
      <Paper
        elevation={3}
        className="glass"
        sx={{
          p: 4,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          width: '100%',
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
            Welcome to Denker
          </Typography>
          <Typography variant="body2" color="text.secondary" align="center" sx={{ mt: 1 }}>
            Your AI-powered desktop assistant
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
        >
          Sign In
        </Button>
        
        <Typography variant="body2" color="text.secondary" align="center">
          Powered by Auth0
        </Typography>
      </Paper>
    </Container>
  );
};

export default Login; 