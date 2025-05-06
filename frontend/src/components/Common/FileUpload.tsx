import React, { useState, useRef } from 'react';
import {
  Box,
  Button,
  Typography,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  IconButton,
  Paper,
  LinearProgress,
  Chip,
} from '@mui/material';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import AttachFileIcon from '@mui/icons-material/AttachFile';
import DeleteIcon from '@mui/icons-material/Delete';
import InsertDriveFileIcon from '@mui/icons-material/InsertDriveFile';
import PictureAsPdfIcon from '@mui/icons-material/PictureAsPdf';
import ImageIcon from '@mui/icons-material/Image';
import DescriptionIcon from '@mui/icons-material/Description';

// Utils
import { formatBytes } from '../../utils/helpers';

interface FileUploadProps {
  onFilesSelected: (files: File[]) => void;
  maxFiles?: number;
  maxSize?: number; // in bytes
  acceptedFileTypes?: string[];
  multiple?: boolean;
  uploadProgress?: number;
  isUploading?: boolean;
  label?: string;
  showPreview?: boolean;
}

const FileUpload: React.FC<FileUploadProps> = ({
  onFilesSelected,
  maxFiles = 5,
  maxSize = 10 * 1024 * 1024, // 10MB default
  acceptedFileTypes = ['*/*'],
  multiple = true,
  uploadProgress = 0,
  isUploading = false,
  label = 'Upload Files',
  showPreview = false,
}) => {
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Handle file selection
  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files || []);
    
    // Check if adding these files would exceed the max files limit
    if (selectedFiles.length + files.length > maxFiles) {
      setError(`You can only upload a maximum of ${maxFiles} files`);
      return;
    }
    
    // Validate file size and type
    const validFiles = files.filter(file => {
      // Check file size
      if (file.size > maxSize) {
        setError(`File ${file.name} exceeds the maximum size of ${formatBytes(maxSize)}`);
        return false;
      }
      
      // Check file type if specific types are required
      if (acceptedFileTypes[0] !== '*/*') {
        const fileType = file.type;
        const isAccepted = acceptedFileTypes.some(type => {
          // Handle wildcards like image/*
          if (type.endsWith('/*')) {
            const category = type.split('/')[0];
            return fileType.startsWith(`${category}/`);
          }
          return type === fileType;
        });
        
        if (!isAccepted) {
          setError(`File ${file.name} is not an accepted file type`);
          return false;
        }
      }
      
      return true;
    });
    
    if (validFiles.length > 0) {
      const newFiles = [...selectedFiles, ...validFiles];
      setSelectedFiles(newFiles);
      onFilesSelected(newFiles);
      setError(null);
    }
    
    // Reset the file input
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  // Handle file removal
  const handleRemoveFile = (index: number) => {
    const newFiles = [...selectedFiles];
    newFiles.splice(index, 1);
    setSelectedFiles(newFiles);
    onFilesSelected(newFiles);
  };

  // Handle click on the upload button
  const handleUploadClick = () => {
    if (fileInputRef.current) {
      fileInputRef.current.click();
    }
  };

  // Get appropriate icon for file type
  const getFileIcon = (file: File) => {
    const fileType = file.type;
    
    if (fileType.startsWith('image/')) {
      return <ImageIcon />;
    } else if (fileType === 'application/pdf') {
      return <PictureAsPdfIcon />;
    } else if (fileType.includes('document') || fileType.includes('text')) {
      return <DescriptionIcon />;
    } else {
      return <InsertDriveFileIcon />;
    }
  };

  return (
    <Box>
      <input
        type="file"
        ref={fileInputRef}
        style={{ display: 'none' }}
        onChange={handleFileChange}
        accept={acceptedFileTypes.join(',')}
        multiple={multiple}
      />
      
      <Button
        variant="outlined"
        startIcon={<CloudUploadIcon />}
        onClick={handleUploadClick}
        disabled={isUploading || selectedFiles.length >= maxFiles}
        fullWidth
        sx={{ mb: 2 }}
      >
        {label}
      </Button>
      
      {error && (
        <Typography color="error" variant="caption" sx={{ display: 'block', mb: 1 }}>
          {error}
        </Typography>
      )}
      
      {isUploading && (
        <Box sx={{ width: '100%', mb: 2 }}>
          <LinearProgress variant="determinate" value={uploadProgress} />
          <Typography variant="caption" sx={{ display: 'block', mt: 0.5 }}>
            Uploading... {uploadProgress}%
          </Typography>
        </Box>
      )}
      
      {showPreview && selectedFiles.length > 0 && (
        <Paper
          variant="outlined"
          sx={{
            mt: 2,
            p: 1,
            backgroundColor: 'rgba(0, 0, 0, 0.05)',
            borderRadius: 1,
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
            <AttachFileIcon fontSize="small" sx={{ mr: 1 }} />
            <Typography variant="body2">
              Selected Files ({selectedFiles.length}/{maxFiles})
            </Typography>
          </Box>
          
          <List dense>
            {selectedFiles.map((file, index) => (
              <ListItem
                key={`${file.name}-${index}`}
                secondaryAction={
                  <IconButton edge="end" onClick={() => handleRemoveFile(index)} size="small">
                    <DeleteIcon fontSize="small" />
                  </IconButton>
                }
              >
                <ListItemIcon sx={{ minWidth: 36 }}>
                  {getFileIcon(file)}
                </ListItemIcon>
                <ListItemText
                  primary={file.name}
                  secondary={formatBytes(file.size)}
                  primaryTypographyProps={{ variant: 'body2', noWrap: true }}
                  secondaryTypographyProps={{ variant: 'caption' }}
                />
              </ListItem>
            ))}
          </List>
        </Paper>
      )}
      
      {showPreview && (
        <Box sx={{ mt: 1 }}>
          <Typography variant="caption" color="text.secondary">
            Max {maxFiles} files, up to {formatBytes(maxSize)} each
          </Typography>
          {acceptedFileTypes[0] !== '*/*' && (
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mt: 0.5 }}>
              {acceptedFileTypes.map((type, index) => (
                <Chip
                  key={index}
                  label={type.replace('*/', 'All ')}
                  size="small"
                  variant="outlined"
                />
              ))}
            </Box>
          )}
        </Box>
      )}
    </Box>
  );
};

export default FileUpload; 