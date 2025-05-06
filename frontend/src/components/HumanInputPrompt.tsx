import React, { useState } from 'react';
import { 
  Box, 
  Paper, 
  Typography, 
  TextField, 
  Button, 
  Divider,
  CircularProgress
} from '@mui/material';
import PersonIcon from '@mui/icons-material/Person';
import SendIcon from '@mui/icons-material/Send';
import CodeIcon from '@mui/icons-material/Code';

interface HumanInputPromptProps {
  toolName: string;
  toolDescription?: string;
  inputPrompt: string;
  onSubmit: (input: string) => void;
  onCancel?: () => void;
  isWaiting?: boolean;
}

/**
 * HumanInputPrompt component displays when the AI assistant needs human input to continue
 * This is typically triggered when a tool with name "_human_input" is called by the agent
 */
const HumanInputPrompt: React.FC<HumanInputPromptProps> = ({ 
  toolName,
  toolDescription,
  inputPrompt,
  onSubmit,
  onCancel,
  isWaiting = false
}) => {
  const [input, setInput] = useState('');

  // Handle input changes
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setInput(e.target.value);
  };

  // Handle form submission
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (input.trim()) {
      onSubmit(input.trim());
      setInput('');
    }
  };

  // Format tool name for display
  const displayToolName = toolName.replace('_human_input', 'Input Required')
                                  .replace(/_/g, ' ')
                                  .split(' ')
                                  .map(word => word.charAt(0).toUpperCase() + word.slice(1))
                                  .join(' ');

  return (
    <Paper 
      elevation={3} 
      sx={{ 
        p: 3, 
        mb: 2,
        border: '1px solid',
        borderColor: 'warning.main',
        borderRadius: 2,
        backgroundColor: theme => theme.palette.mode === 'dark' 
          ? 'rgba(255, 167, 38, 0.08)'
          : 'rgba(255, 167, 38, 0.04)'
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
        <PersonIcon color="warning" sx={{ mr: 1 }} />
        <Typography variant="h6" color="warning.main">
          {displayToolName}
        </Typography>
      </Box>
      
      <Divider sx={{ mb: 2 }} />
      
      <Typography variant="body1" paragraph>
        {inputPrompt}
      </Typography>
      
      {toolDescription && (
        <Box sx={{ 
          display: 'flex', 
          alignItems: 'flex-start', 
          mb: 2, 
          p: 1.5, 
          bgcolor: 'background.paper',
          borderRadius: 1,
          border: '1px solid',
          borderColor: 'divider'
        }}>
          <CodeIcon color="info" sx={{ mr: 1, mt: 0.3 }} />
          <Typography variant="body2" color="text.secondary">
            {toolDescription}
          </Typography>
        </Box>
      )}
      
      <form onSubmit={handleSubmit}>
        <TextField
          fullWidth
          multiline
          rows={3}
          variant="outlined"
          placeholder="Type your input here..."
          value={input}
          onChange={handleInputChange}
          sx={{ mb: 2 }}
          disabled={isWaiting}
        />
        
        <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1 }}>
          {onCancel && (
            <Button 
              variant="outlined" 
              onClick={onCancel}
              disabled={isWaiting}
            >
              Skip
            </Button>
          )}
          <Button 
            variant="contained" 
            color="warning"
            type="submit" 
            endIcon={isWaiting ? <CircularProgress size={16} color="inherit" /> : <SendIcon />}
            disabled={!input.trim() || isWaiting}
          >
            Submit Input
          </Button>
        </Box>
      </form>
    </Paper>
  );
};

export default HumanInputPrompt; 