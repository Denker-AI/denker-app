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
  Menu,
  MenuItem,
  ListItemIcon,
  ListItemText,
  Divider,
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
import SmartToyIcon from '@mui/icons-material/SmartToy';
import GroupsIcon from '@mui/icons-material/Groups';
import PersonIcon from '@mui/icons-material/Person';
import SearchIcon from '@mui/icons-material/Search';
import CreateIcon from '@mui/icons-material/Create';
import EditIcon from '@mui/icons-material/Edit';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import EditNoteIcon from '@mui/icons-material/EditNote';

/**
 * Properties for the InputBox component
 */
interface InputBoxProps {
  onSendMessage: (content: string, files?: File[], mode?: 'multiagent' | 'single', singleAgentType?: string) => Promise<void>;
  isLoading: boolean;
  onStopProcessing?: () => void;
}

/**
 * Enhanced message input box component with attachments and mode selection
 */
const InputBoxNew: React.FC<InputBoxProps> = ({
  onSendMessage,
  isLoading,
  onStopProcessing,
}) => {
  const theme = useTheme();
  const [message, setMessage] = useState('');
  const [files, setFiles] = useState<File[]>([]);
  const [mode, setMode] = useState<'multiagent' | 'single'>('multiagent');
  const [singleAgentType, setSingleAgentType] = useState<string>('researcher');
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  // Focus input on component mount
  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.focus();
    }
  }, []);
  
  // Handle input changes
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
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

  // Handle mode menu
  const handleModeMenuClick = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleModeMenuClose = () => {
    setAnchorEl(null);
  };

  const handleModeSelect = (selectedMode: 'multiagent' | 'single', agentType?: string) => {
    setMode(selectedMode);
    if (selectedMode === 'single' && agentType) {
      setSingleAgentType(agentType);
    }
    handleModeMenuClose();
  };
  
  // Handle sending a message
  const handleSendMessage = async () => {
    if ((message.trim() || files.length > 0) && !isLoading) {
      try {
        const messageToSend = message;
        const filesToSend = files.length > 0 ? [...files] : undefined;
        
        console.log('[InputBoxNew] Sending message:', messageToSend);
        console.log('[InputBoxNew] Sending files:', filesToSend);
        console.log('[InputBoxNew] Mode:', mode, 'Agent type:', singleAgentType);
        
        // Clear input immediately for better UX
        setMessage('');
        setFiles([]);
        
        // Process the message asynchronously with mode information
        onSendMessage(messageToSend, filesToSend, mode, mode === 'single' ? singleAgentType : undefined).catch(error => {
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

  // Get mode display information
  const getModeDisplayInfo = () => {
    if (mode === 'multiagent') {
      return {
        icon: <GroupsIcon />,
        text: 'Multi-Agent',
        color: 'primary' as const
      };
    } else {
      const agentInfo = {
        researcher: { icon: <SearchIcon />, text: 'Researcher' },
        creator: { icon: <CreateIcon />, text: 'Creator' },
        editor: { icon: <EditIcon />, text: 'Editor' }
      };
      return {
        icon: agentInfo[singleAgentType as keyof typeof agentInfo]?.icon || <PersonIcon />,
        text: agentInfo[singleAgentType as keyof typeof agentInfo]?.text || 'Single Agent',
        color: 'secondary' as const
      };
    }
  };

  const modeDisplayInfo = getModeDisplayInfo();
  


  return (
    <Paper
      elevation={0}
      sx={{
        p: 2,
        m: 2,
        borderRadius: 2,
        backgroundColor: 'transparent',
        border: '0.25px solid #C0C0C0', // Even thinner silver lining
        boxShadow: 'none',
      }}
    >
      {/* Mode Selection Menu */}
      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={handleModeMenuClose}
        anchorOrigin={{
          vertical: 'top',
          horizontal: 'left',
        }}
        transformOrigin={{
          vertical: 'bottom',
          horizontal: 'left',
        }}
        PaperProps={{
          sx: {
            minWidth: '180px', // Smaller menu width
          }
        }}
      >
        <MenuItem 
          onClick={() => handleModeSelect('multiagent')}
          sx={{ py: 0.5, minHeight: '28px' }} // Reduced padding for tighter spacing
        >
          <ListItemIcon sx={{ minWidth: '24px' }}> {/* Match button icon area */}
            <GroupsIcon sx={{ fontSize: '14px' }} color="primary" /> {/* Match button icon size */}
          </ListItemIcon>
          <ListItemText 
            primary="Multi-Agent"
            primaryTypographyProps={{ fontSize: '0.75rem' }} // Match button font size
          />
        </MenuItem>
        <Divider />
        <MenuItem 
          disabled
          sx={{ py: 0.5, opacity: 0.5, cursor: 'not-allowed', minHeight: '28px' }} // Reduced padding
        >
          <ListItemIcon sx={{ minWidth: '24px' }}> {/* Match button icon area */}
            <SearchIcon sx={{ fontSize: '14px', color: theme.palette.text.disabled }} /> {/* Match button icon size */}
          </ListItemIcon>
          <ListItemText 
            primary="Researcher"
            primaryTypographyProps={{ fontSize: '0.75rem', color: theme.palette.text.disabled }} // Match button font size
          />
        </MenuItem>
        <MenuItem 
          disabled
          sx={{ py: 0.5, opacity: 0.5, cursor: 'not-allowed', minHeight: '28px' }} // Reduced padding
        >
          <ListItemIcon sx={{ minWidth: '24px' }}> {/* Match button icon area */}
            <CreateIcon sx={{ fontSize: '14px', color: theme.palette.text.disabled }} /> {/* Match button icon size */}
          </ListItemIcon>
          <ListItemText 
            primary="Creator"
            primaryTypographyProps={{ fontSize: '0.75rem', color: theme.palette.text.disabled }} // Match button font size
          />
        </MenuItem>
        <MenuItem 
          disabled
          sx={{ py: 0.5, opacity: 0.5, cursor: 'not-allowed', minHeight: '28px' }} // Reduced padding
        >
          <ListItemIcon sx={{ minWidth: '24px' }}> {/* Match button icon area */}
            <EditNoteIcon sx={{ fontSize: '14px', color: theme.palette.text.disabled }} /> {/* Match button icon size */}
          </ListItemIcon>
          <ListItemText 
            primary="Editor"
            primaryTypographyProps={{ fontSize: '0.75rem', color: theme.palette.text.disabled }} // Match button font size
          />
        </MenuItem>
      </Menu>

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
      
      {/* Input area - Unified design like Cursor */}
      <Box sx={{ 
        border: 'none',
        borderRadius: 2,
        p: 1,
        backgroundColor: 'transparent',
        position: 'relative'
      }}>
        {/* Main text input area - multiline with auto-grow */}
        <TextField
          fullWidth
          multiline
          maxRows={6}
          placeholder="Research, write, edit anything..."
          value={message}
          onChange={handleInputChange}
          onKeyDown={handleKeyPress}
          disabled={isLoading}
          variant="standard"
          inputRef={inputRef}
          InputProps={{
            disableUnderline: true,
            sx: { 
              fontSize: '1rem',
              lineHeight: 1.5,
            },
          }}
          sx={{
            '& .MuiInputBase-input': {
              padding: '8px 0',
              resize: 'none',
              '&::placeholder': {
                fontStyle: 'italic',
                opacity: 0.6,
              },
            },
            mb: 2,
          }}
        />

        {/* Bottom row - Agent button on left, attachment and send on right */}
        <Box sx={{ 
          display: 'flex', 
          justifyContent: 'space-between',
          alignItems: 'center',
          pt: 1,
          borderTop: `1px solid ${theme.palette.mode === 'dark' ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.08)'}`,
        }}>
          {/* Left side - Mode selection button */}
          <Tooltip title={`Current mode: ${modeDisplayInfo.text}. Click to change mode.`}>
            <Button
              onClick={handleModeMenuClick}
              disabled={isLoading}
              size="small"
              variant="text"
              sx={{ 
                minWidth: 'auto',
                px: 1,
                py: 0.5,
                fontSize: '0.75rem',
                borderRadius: '6px',
                textTransform: 'none',
                display: 'flex',
                alignItems: 'center',
                gap: 0.5,
                height: '28px',
                color: theme.palette.text.secondary,
                border: `1px solid ${theme.palette.divider}`,
                '&:hover': {
                  backgroundColor: theme.palette.action.hover,
                  borderColor: theme.palette.primary.main,
                }
              }}
              endIcon={<KeyboardArrowDownIcon sx={{ fontSize: '14px', color: theme.palette.text.secondary }} />}
            >
              {React.cloneElement(modeDisplayInfo.icon, { sx: { fontSize: '14px', color: theme.palette.text.secondary } })}
              <Typography variant="caption" sx={{ fontSize: '0.75rem', lineHeight: 1, color: theme.palette.text.secondary }}>
                {modeDisplayInfo.text}
              </Typography>
            </Button>
          </Tooltip>

          {/* Right side - Attachment and Send buttons */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            {/* File Attachment Button */}
            <Tooltip title="Attach files">
              <Button
                onClick={handleFileButtonClick}
                disabled={isLoading}
                variant="outlined"
                sx={{
                  minWidth: 0,
                  padding: '6px',
                  borderRadius: '8px',
                  width: '32px',
                  height: '32px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  borderColor: theme.palette.divider,
                  color: theme.palette.text.secondary,
                  '&:hover': {
                    backgroundColor: theme.palette.action.hover,
                    borderColor: theme.palette.primary.main,
                  }
                }}
              >
                <AttachFileIcon sx={{ fontSize: '18px' }} />
              </Button>
            </Tooltip>

            {/* Send/Stop Button */}
            <Button
              color="primary"
              disabled={isLoading ? false : (!message.trim() && files.length === 0)}
              onClick={isLoading ? handleStop : handleSendMessage}
              variant="contained"
              sx={{
                minWidth: 0,
                padding: '6px',
                borderRadius: '8px',
                width: '32px',
                height: '32px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              {isLoading ? 
                <StopIcon sx={{ fontSize: '18px' }} /> : 
                <ArrowUpwardIcon sx={{ fontSize: '18px' }} />
              }
            </Button>
          </Box>
        </Box>
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