import React from 'react';
import { Box, Typography } from '@mui/material';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';

interface ErrorIndicatorProps {
  message: string;
}

const ErrorIndicator: React.FC<ErrorIndicatorProps> = ({ message }) => {
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
      <ErrorOutlineIcon sx={{ fontSize: 48, color: 'error.main' }} />
      <Typography 
        variant="body1" 
        color="error"
        sx={{ mt: 2, textAlign: 'center' }}
      >
        {message}
      </Typography>
    </Box>
  );
};

export default ErrorIndicator; 