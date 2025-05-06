import React, { useState } from 'react';
import { 
  Box, 
  Paper, 
  Typography, 
  TextField, 
  Button, 
  List, 
  ListItem,
  ListItemIcon,
  ListItemText,
  Divider
} from '@mui/material';
import HelpOutlineIcon from '@mui/icons-material/HelpOutline';
import SendIcon from '@mui/icons-material/Send';

interface ClarificationPromptProps {
  questions: string[];
  onSubmit: (answers: string) => void;
  onCancel?: () => void;
}

/**
 * ClarificationPrompt component displays questions from the agent and allows the user to respond
 * with additional information when the agent needs clarification
 */
const ClarificationPrompt: React.FC<ClarificationPromptProps> = ({ 
  questions, 
  onSubmit,
  onCancel
}) => {
  const [answer, setAnswer] = useState('');

  // Handle input changes
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setAnswer(e.target.value);
  };

  // Handle form submission
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (answer.trim()) {
      onSubmit(answer.trim());
      setAnswer('');
    }
  };

  return (
    <Paper 
      elevation={3} 
      sx={{ 
        p: 3, 
        mb: 2,
        border: '1px solid',
        borderColor: 'primary.main',
        borderRadius: 2,
        backgroundColor: theme => theme.palette.mode === 'dark' 
          ? 'rgba(25, 118, 210, 0.08)'
          : 'rgba(25, 118, 210, 0.04)'
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
        <HelpOutlineIcon color="primary" sx={{ mr: 1 }} />
        <Typography variant="h6" color="primary">
          I Need Some Clarification
        </Typography>
      </Box>
      
      <Divider sx={{ mb: 2 }} />
      
      <Typography variant="body1" paragraph>
        To better assist you, I need some additional information:
      </Typography>
      
      <List sx={{ mb: 2 }}>
        {questions.map((question, index) => (
          <ListItem key={index} sx={{ py: 0.5 }}>
            <ListItemIcon sx={{ minWidth: 32 }}>
              <Typography variant="body1" color="primary" fontWeight="bold">
                {index + 1}.
              </Typography>
            </ListItemIcon>
            <ListItemText primary={question} />
          </ListItem>
        ))}
      </List>
      
      <form onSubmit={handleSubmit}>
        <TextField
          fullWidth
          multiline
          rows={3}
          variant="outlined"
          placeholder="Type your answer here..."
          value={answer}
          onChange={handleInputChange}
          sx={{ mb: 2 }}
        />
        
        <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1 }}>
          {onCancel && (
            <Button 
              variant="outlined" 
              onClick={onCancel}
            >
              Skip
            </Button>
          )}
          <Button 
            variant="contained" 
            type="submit" 
            endIcon={<SendIcon />}
            disabled={!answer.trim()}
          >
            Send Clarification
          </Button>
        </Box>
      </form>
    </Paper>
  );
};

export default ClarificationPrompt; 