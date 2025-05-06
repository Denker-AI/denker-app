import React from 'react';
import { Box, Typography, Button, Divider } from '@mui/material';
import FileSystemActivityLog from './FileSystemActivityLog';
import { useFileSystemActivity } from './FileSystemActivityProvider';

interface ChatFileSystemActivityProps {
  messageId?: string;
}

/**
 * Component for displaying filesystem activity in the chat area
 * Shows all file operations and enables permission controls
 */
const ChatFileSystemActivity: React.FC<ChatFileSystemActivityProps> = ({ messageId }) => {
  const { operations, approveOperation, denyOperation, clearOperations } = useFileSystemActivity();
  
  // Check if we have any active operations to display
  if (operations.length === 0) {
    return null;
  }
  
  // Check if we have any pending operations that need attention
  const pendingOperations = operations.filter(op => op.status === 'pending' && op.requiresPermission);
  const hasPendingOperations = pendingOperations.length > 0;
  
  return (
    <Box sx={{ 
      my: 2,
      p: 2, 
      borderRadius: 1,
      border: '1px solid',
      borderColor: hasPendingOperations ? 'warning.main' : 'divider'
    }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
        <Typography variant="subtitle1" fontWeight="medium">
          Filesystem Operations {hasPendingOperations && `(${pendingOperations.length} pending)`}
        </Typography>
        
        <Button 
          size="small" 
          variant="text" 
          color="inherit"
          onClick={clearOperations}
        >
          Clear History
        </Button>
      </Box>
      
      <Divider sx={{ mb: 2 }} />
      
      <FileSystemActivityLog 
        operations={operations}
        onApprove={(operation) => approveOperation(operation.id)}
        onDeny={(operation) => denyOperation(operation.id)} 
      />
    </Box>
  );
};

export default ChatFileSystemActivity; 