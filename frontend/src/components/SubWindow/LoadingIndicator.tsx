import React from 'react';
import { Box, CircularProgress, Typography } from '@mui/material';

interface LoadingIndicatorProps {
  message?: string;
}

const LoadingIndicator: React.FC<LoadingIndicatorProps> = ({ 
  message = 'Loading options...' 
}) => {
  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100%',
        p: 4,
      }}
    >
      <CircularProgress size={40} thickness={4} />
      <Typography 
        variant="body1" 
        color="text.secondary" 
        sx={{ mt: 2, textAlign: 'center' }}
      >
        {message}
      </Typography>
    </Box>
  );
};

export default LoadingIndicator; 