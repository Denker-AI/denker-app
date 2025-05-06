import React, { useState, useRef, useEffect } from 'react';
import {
  Box,
  TextField,
  Button,
  IconButton,
  Paper,
  Tooltip,
  Typography,
  useTheme,
  Chip,
  CircularProgress,
} from '@mui/material';
import { styled } from '@mui/material/styles';
import SendIcon from '@mui/icons-material/Send';
import AttachFileIcon from '@mui/icons-material/AttachFile';
import InsertDriveFileIcon from '@mui/icons-material/InsertDriveFile';
import CloseIcon from '@mui/icons-material/Close';
import ArrowUpwardIcon from '@mui/icons-material/ArrowUpward';
import StopIcon from '@mui/icons-material/Stop';
import MicIcon from '@mui/icons-material/Mic';
import DeleteIcon from '@mui/icons-material/Delete';

/**
 * Properties for the InputBox component
 */
interface InputBoxProps {
  onSendMessage: (content: string, files?: File[]) => Promise<void>;
  isLoading: boolean;
  onStopProcessing?: () => void;
}

/**
 * Enhanced message input box component with attachments
 */
const InputBoxNew: React.FC<InputBoxProps> = ({
  onSendMessage,
  isLoading,
  onStopProcessing,
}) => {
  const theme = useTheme();
  const [message, setMessage] = useState('');
  const [files, setFiles] = useState<File[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  // Focus input on component mount
  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.focus();
    }
  }, []);
  
  // Handle input changes
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setMessage(e.target.value);
  };
  
  // Handle key presses (e.g., Enter to send)
  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };
  
  // Handle file selection
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = e.target.files;
    
    if (selectedFiles && selectedFiles.length > 0) {
      // Add new files to the existing array
      const newFiles = Array.from(selectedFiles);
      setFiles((prevFiles) => [...prevFiles, ...newFiles]);
      
      // Clear the input value so the same file can be selected again
      e.target.value = '';
      
      // Re-focus the text input
      if (inputRef.current) {
        inputRef.current.focus();
      }
    }
  };
  
  // Handle file removal
  const handleRemoveFile = (fileToRemove: File) => {
    setFiles(files.filter(f => f !== fileToRemove));
    
    // Re-focus the text input
    if (inputRef.current) {
      inputRef.current.focus();
    }
  };
  
  // Handle clicking the file upload button
  const handleFileButtonClick = () => {
    fileInputRef.current?.click();
  };
  
  // Handle sending a message
  const handleSendMessage = async () => {
    if ((message.trim() || files.length > 0) && !isLoading) {
      try {
        const messageToSend = message;
        const filesToSend = files.length > 0 ? [...files] : undefined;
        
        console.log('[InputBoxNew] Sending message:', messageToSend);
        console.log('[InputBoxNew] Sending files:', filesToSend);
        
        // Clear input immediately for better UX
        setMessage('');
        setFiles([]);
        
        // Process the message asynchronously
        onSendMessage(messageToSend, filesToSend).catch(error => {
          console.error('[InputBoxNew] Error sending message:', error);
        });
        
        // Re-focus the input field immediately
        if (inputRef.current) {
          inputRef.current.focus();
        }
      } catch (error) {
        console.error('[InputBoxNew] Error preparing message:', error);
        
        // Re-focus even on error
        if (inputRef.current) {
          inputRef.current.focus();
        }
      }
    }
  };
  
  const handleStop = () => {
    if (onStopProcessing) {
      console.log("[InputBoxNew] Stop button clicked");
      onStopProcessing();
    }
  };
  
  // Format file size
  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return bytes + ' B';
    else if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
    else return (bytes / 1048576).toFixed(1) + ' MB';
  };
  
  // Memoize the endAdornment to prevent unnecessary rerenders
  const endAdornment = (
    <Box sx={{ display: 'flex', alignItems: 'center' }}>
      <Tooltip title="Attach files">
        <IconButton
          onClick={handleFileButtonClick}
          disabled={isLoading}
          size="small"
          sx={{ mr: 0.5 }}
        >
          <AttachFileIcon />
        </IconButton>
      </Tooltip>
    </Box>
  );
  
  return (
    <Paper
      elevation={3}
      sx={{
        p: 2,
        m: 2,
        borderRadius: 2,
        backgroundColor: theme.palette.background.paper,
        boxShadow: '0 2px 10px rgba(0, 0, 0, 0.1)',
      }}
    >
      {/* File attachment display */}
      {files.length > 0 && (
        <Box sx={{ mb: 2 }}>
          <Typography variant="subtitle2" sx={{ mb: 1 }}>
            Attachments ({files.length})
          </Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
            {files.map((file, index) => (
              <Chip
                key={`${file.name}-${index}`}
                icon={<InsertDriveFileIcon />}
                label={`${file.name} (${formatFileSize(file.size)})`}
                onDelete={() => handleRemoveFile(file)}
                deleteIcon={<CloseIcon />}
                variant="outlined"
                sx={{ maxWidth: 250 }}
              />
            ))}
          </Box>
        </Box>
      )}
      
      {/* Input area */}
      <Box sx={{ display: 'flex', alignItems: 'center' }}>
        <TextField
          fullWidth
          multiline
          maxRows={5}
          placeholder="Type a message..."
          value={message}
          onChange={handleInputChange}
          onKeyDown={handleKeyPress}
          disabled={isLoading}
          variant="outlined"
          size="small"
          inputRef={inputRef}
          InputProps={{
            sx: { pr: 0.5 },
            endAdornment: endAdornment,
          }}
          sx={{
            '& .MuiOutlinedInput-root': {
              paddingRight: 0.5,
            },
            '& textarea': {
              '&::placeholder': {
                fontStyle: 'italic',
              },
            },
          }}
        />
        
        <Button
          color="primary"
          disabled={isLoading ? false : (!message.trim() && files.length === 0)}
          onClick={isLoading ? handleStop : handleSendMessage}
          variant="contained"
          sx={{
            minWidth: 0,
            ml: 1,
            padding: '8px',
            borderRadius: '50%',
            width: '40px',
            height: '40px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          {isLoading ? 
            <StopIcon sx={{ verticalAlign: 'middle' }} /> : 
            <ArrowUpwardIcon sx={{ verticalAlign: 'middle' }} />
          }
        </Button>
      </Box>
      
      {/* Hidden file input */}
      <input
        type="file"
        multiple
        ref={fileInputRef}
        onChange={handleFileChange}
        style={{ display: 'none' }}
      />
    </Paper>
  );
};

export default InputBoxNew; 