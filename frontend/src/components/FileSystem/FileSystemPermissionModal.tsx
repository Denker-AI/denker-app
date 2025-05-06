import React, { useState, useEffect } from 'react';
import { 
  Modal, 
  Box, 
  Typography, 
  Button, 
  CircularProgress,
  Paper,
  Tooltip,
  IconButton,
  Chip
} from '@mui/material';
import { Info as InfoIcon } from '@mui/icons-material';

interface FileSystemPermissionProps {
  isOpen: boolean;
  request: {
    operation_id: string;
    operation: string;
    path: string;
    arguments: any;
  } | null;
  onResponse: (operationId: string, approved: boolean) => void;
  onTimeout: () => void;
}

/**
 * Modal component that shows filesystem permission requests and allows users
 * to approve or deny them
 */
const FileSystemPermissionModal: React.FC<FileSystemPermissionProps> = ({
  isOpen,
  request,
  onResponse,
  onTimeout
}) => {
  const [timeLeft, setTimeLeft] = useState(60);
  
  // Reset timer when a new request comes in
  useEffect(() => {
    if (isOpen && request) {
      setTimeLeft(60);
    }
  }, [isOpen, request]);
  
  // Handle countdown timer
  useEffect(() => {
    if (!isOpen || !request) return;
    
    const timer = setInterval(() => {
      setTimeLeft(prev => {
        if (prev <= 1) {
          clearInterval(timer);
          onTimeout();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    
    return () => clearInterval(timer);
  }, [isOpen, onTimeout, request]);
  
  if (!request) return null;
  
  // Format operation for display
  const getOperationDisplay = () => {
    switch (request.operation) {
      case 'write_file':
        return 'Write to file';
      case 'read_file':
        return 'Read file';
      case 'create_directory':
        return 'Create directory';
      case 'list_directory':
        return 'List directory contents';
      case 'move_file':
        return 'Move/rename file';
      default:
        return request.operation;
    }
  };
  
  // Generate content preview for write operations
  const getContentPreview = () => {
    if (request.operation === 'write_file' && request.arguments?.content) {
      const content = request.arguments.content;
      return content.length > 300 
        ? content.substring(0, 300) + '...' 
        : content;
    }
    return null;
  };
  
  // Get file path display, handling both single path and source/destination
  const getPathDisplay = () => {
    if (request.operation === 'move_file') {
      const source = request.arguments?.source || '';
      const destination = request.arguments?.destination || '';
      return (
        <>
          <Typography sx={{ mt: 1 }}>
            <strong>From:</strong> {source}
          </Typography>
          <Typography sx={{ mt: 0.5 }}>
            <strong>To:</strong> {destination}
          </Typography>
        </>
      );
    }
    
    return (
      <Typography sx={{ mt: 1, wordBreak: 'break-all' }}>
        <strong>Path:</strong> {request.path}
      </Typography>
    );
  };
  
  // Severity indication based on operation
  const getSeverityIndicator = () => {
    // Higher risk operations
    if (['write_file', 'move_file'].includes(request.operation)) {
      return <Chip color="error" size="small" label="Modifies files" sx={{ ml: 1 }} />;
    }
    
    // Medium risk operations
    if (['create_directory'].includes(request.operation)) {
      return <Chip color="warning" size="small" label="Creates structure" sx={{ ml: 1 }} />;
    }
    
    // Safe operations
    return <Chip color="success" size="small" label="Read only" sx={{ ml: 1 }} />;
  };
  
  return (
    <Modal open={isOpen} onClose={() => onResponse(request.operation_id, false)}>
      <Paper 
        elevation={5}
        sx={{ 
          position: 'absolute', 
          top: '50%', 
          left: '50%', 
          transform: 'translate(-50%, -50%)',
          width: { xs: '90%', sm: 500 },
          maxHeight: '90vh',
          overflow: 'auto',
          p: 3,
          borderRadius: 2
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
          <Typography variant="h6" component="h2">
            Permission Request
          </Typography>
          <Tooltip title="The AI assistant is requesting permission to perform a file operation. You can approve or deny this request.">
            <IconButton size="small" sx={{ ml: 1 }}>
              <InfoIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>
        
        <Box sx={{ mb: 3 }}>
          <Box sx={{ display: 'flex', alignItems: 'center' }}>
            <Typography variant="subtitle1" fontWeight="bold">
              {getOperationDisplay()}
            </Typography>
            {getSeverityIndicator()}
          </Box>
          
          {getPathDisplay()}
        </Box>
        
        {getContentPreview() && (
          <Box sx={{ mt: 2, mb: 3 }}>
            <Typography variant="subtitle2" gutterBottom>
              Content Preview:
            </Typography>
            <Box sx={{ 
              maxHeight: 150, 
              overflow: 'auto', 
              bgcolor: 'grey.100', 
              p: 1.5,
              borderRadius: 1,
              fontFamily: 'monospace',
              fontSize: '0.75rem',
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word'
            }}>
              {getContentPreview()}
            </Box>
          </Box>
        )}
        
        <Box sx={{ 
          display: 'flex', 
          justifyContent: 'space-between', 
          alignItems: 'center',
          mt: 3 
        }}>
          <Box sx={{ display: 'flex', alignItems: 'center' }}>
            <CircularProgress 
              variant="determinate" 
              value={(timeLeft / 60) * 100} 
              size={24} 
              sx={{ mr: 1.5 }} 
            />
            <Typography variant="body2">
              {timeLeft}s remaining
            </Typography>
          </Box>
          
          <Box>
            <Button 
              variant="outlined" 
              color="error" 
              onClick={() => onResponse(request.operation_id, false)}
              sx={{ mr: 2 }}
            >
              Deny
            </Button>
            <Button 
              variant="contained" 
              color="primary" 
              onClick={() => onResponse(request.operation_id, true)}
            >
              Approve
            </Button>
          </Box>
        </Box>
      </Paper>
    </Modal>
  );
};

export default FileSystemPermissionModal; 