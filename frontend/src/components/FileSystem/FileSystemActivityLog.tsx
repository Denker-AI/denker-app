import React, { useState, useEffect } from 'react';
import { 
  Box, 
  Typography, 
  Paper, 
  Chip, 
  Button, 
  CircularProgress,
  Stack,
  Divider,
  Collapse
} from '@mui/material';
import { 
  InsertDriveFile as FileIcon,
  Folder as FolderIcon,
  Search as SearchIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  Warning as WarningIcon,
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon
} from '@mui/icons-material';
import { useFileSystemPermission } from './FileSystemPermissionProvider';

// Define types for filesystem operations
export type FileSystemOperationType = 
  'read_file' | 
  'write_file' | 
  'search_files' | 
  'list_directory' | 
  'create_directory' |
  'move_file' | 
  'delete_file' | 
  'edit_file';

// Operation details
export interface FileSystemOperation {
  id: string;
  type: FileSystemOperationType;
  path: string;
  status: 'pending' | 'approved' | 'denied' | 'completed' | 'failed';
  timestamp: string;
  details?: string;
  requiresPermission: boolean;
  isPending?: boolean;
}

interface FileSystemActivityLogProps {
  operations: FileSystemOperation[];
  onApprove?: (operation: FileSystemOperation) => void;
  onDeny?: (operation: FileSystemOperation) => void;
}

/**
 * Component to display all filesystem activities inline in the chat
 * Shows a history of operations and allows user to approve/deny pending ones
 */
const FileSystemActivityLog: React.FC<FileSystemActivityLogProps> = ({ 
  operations, 
  onApprove, 
  onDeny 
}) => {
  const [expandedItems, setExpandedItems] = useState<Record<string, boolean>>({});
  const { currentRequest } = useFileSystemPermission();

  // Toggle expansion state for an operation
  const toggleExpand = (id: string) => {
    setExpandedItems(prev => ({
      ...prev,
      [id]: !prev[id]
    }));
  };

  // Get icon based on operation type
  const getOperationIcon = (type: FileSystemOperationType) => {
    switch (type) {
      case 'read_file':
        return <FileIcon fontSize="small" color="info" />;
      case 'write_file':
        return <FileIcon fontSize="small" color="warning" />;
      case 'search_files':
        return <SearchIcon fontSize="small" color="info" />;
      case 'list_directory':
        return <FolderIcon fontSize="small" color="info" />;
      case 'create_directory':
        return <FolderIcon fontSize="small" color="warning" />;
      case 'edit_file':
        return <EditIcon fontSize="small" color="warning" />;
      case 'delete_file':
        return <DeleteIcon fontSize="small" color="error" />;
      case 'move_file':
        return <FileIcon fontSize="small" color="warning" />;
      default:
        return <FileIcon fontSize="small" />;
    }
  };

  // Get label for operation type
  const getOperationLabel = (type: FileSystemOperationType) => {
    switch (type) {
      case 'read_file':
        return 'Reading file';
      case 'write_file':
        return 'Creating file';
      case 'search_files':
        return 'Searching files';
      case 'list_directory':
        return 'Listing directory';
      case 'create_directory':
        return 'Creating directory';
      case 'edit_file':
        return 'Editing file';
      case 'delete_file':
        return 'Deleting file';
      case 'move_file':
        return 'Moving file';
      default:
        return type.replace('_', ' ');
    }
  };

  // Get status color
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'pending':
        return 'warning';
      case 'approved':
        return 'info';
      case 'completed':
        return 'success';
      case 'denied':
      case 'failed':
        return 'error';
      default:
        return 'default';
    }
  };

  // Get description based on operation type
  const getOperationDescription = (operation: FileSystemOperation) => {
    const fileName = operation.path.split('/').pop();
    const dirPath = operation.path.split('/').slice(0, -1).join('/') || '/';

    switch (operation.type) {
      case 'read_file':
        return `Reading contents of "${fileName}"`;
      case 'write_file':
        return `Creating new file "${fileName}" in ${dirPath}`;
      case 'search_files':
        return `Searching for ${operation.details || 'files'}`;
      case 'list_directory':
        return `Listing contents of directory "${operation.path}"`;
      case 'create_directory':
        return `Creating new directory "${fileName}" in ${dirPath}`;
      case 'edit_file':
        return `Modifying file "${fileName}"`;
      case 'delete_file':
        return `Deleting file "${fileName}"`;
      case 'move_file':
        const destPath = operation.details?.split(' to ')[1] || '';
        const destName = destPath.split('/').pop();
        return `Moving "${fileName}" to "${destName}"`;
      default:
        return `Operation on ${operation.path}`;
    }
  };

  // Check if there are any pending operations that need attention
  const hasPendingOperations = operations.some(op => op.status === 'pending' && op.requiresPermission);

  if (operations.length === 0) {
    return null;
  }

  return (
    <Box sx={{ my: 2 }}>
      {hasPendingOperations && (
        <Box sx={{ mb: 2, p: 1, bgcolor: 'warning.light', borderRadius: 1 }}>
          <Typography variant="subtitle2" sx={{ display: 'flex', alignItems: 'center' }}>
            <WarningIcon fontSize="small" sx={{ mr: 1 }} />
            Filesystem operations requiring your permission
          </Typography>
        </Box>
      )}

      {operations.map((operation) => (
        <Paper
          key={operation.id}
          variant="outlined"
          sx={{
            mb: 1,
            p: 1.5,
            borderLeft: 4,
            borderLeftColor: `${getStatusColor(operation.status)}.main`,
            bgcolor: operation.status === 'pending' ? 'action.hover' : 'background.paper',
          }}
        >
          <Stack direction="row" alignItems="center" spacing={1}>
            {getOperationIcon(operation.type)}
            
            <Typography variant="body1" sx={{ fontWeight: 'medium', flexGrow: 1 }}>
              {getOperationLabel(operation.type)}
            </Typography>
            
            <Chip 
              size="small" 
              label={operation.status} 
              color={getStatusColor(operation.status)}
            />
            
            <Button
              size="small"
              variant="text"
              onClick={() => toggleExpand(operation.id)}
              endIcon={expandedItems[operation.id] ? <ExpandLessIcon /> : <ExpandMoreIcon />}
            >
              {expandedItems[operation.id] ? 'Less' : 'More'}
            </Button>
          </Stack>
          
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
            {getOperationDescription(operation)}
          </Typography>

          <Collapse in={expandedItems[operation.id]} timeout="auto" unmountOnExit>
            <Box sx={{ mt: 1.5, pl: 1 }}>
              <Typography variant="caption" sx={{ display: 'block', mb: 0.5 }}>
                <strong>Path:</strong> {operation.path}
              </Typography>
              
              {operation.details && (
                <Typography variant="caption" sx={{ display: 'block', mb: 0.5 }}>
                  <strong>Details:</strong> {operation.details}
                </Typography>
              )}
              
              <Typography variant="caption" sx={{ display: 'block', mb: 0.5 }}>
                <strong>Time:</strong> {new Date(operation.timestamp).toLocaleTimeString()}
              </Typography>
            </Box>
          </Collapse>

          {operation.status === 'pending' && operation.requiresPermission && (
            <Box sx={{ mt: 1.5, display: 'flex', justifyContent: 'flex-end', gap: 1 }}>
              {operation.isPending && (
                <CircularProgress size={24} sx={{ mr: 1 }} />
              )}
              <Button
                size="small"
                variant="outlined"
                color="error"
                onClick={() => onDeny && onDeny(operation)}
              >
                Deny
              </Button>
              <Button
                size="small"
                variant="contained"
                color="primary"
                onClick={() => onApprove && onApprove(operation)}
              >
                Approve
              </Button>
            </Box>
          )}
        </Paper>
      ))}
    </Box>
  );
};

export default FileSystemActivityLog; 