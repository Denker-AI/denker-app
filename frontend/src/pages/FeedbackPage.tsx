import React, { useState } from 'react';
import {
  Box,
  Typography,
  TextField,
  Button,
  Paper,
  IconButton,
  FormControl,
  FormControlLabel,
  RadioGroup,
  Radio,
  Snackbar,
  Alert,
  useTheme,
  CircularProgress,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { useNavigate } from 'react-router-dom';



// Types
type FeedbackType = 'bug' | 'feature' | 'general';

const FeedbackPage: React.FC = () => {
  const theme = useTheme();
  const navigate = useNavigate();
  
  // Form state
  const [feedbackType, setFeedbackType] = useState<FeedbackType>('general');
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  
  // UI state
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [alert, setAlert] = useState<{
    open: boolean;
    message: string;
    severity: 'success' | 'error';
  }>({
    open: false,
    message: '',
    severity: 'success',
  });
  
  // Handle form submission
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!title || !description) {
      setAlert({
        open: true,
        message: 'Please fill in all required fields',
        severity: 'error',
      });
      return;
    }
    
    setIsSubmitting(true);
    
    try {
      // Create email content
      const emailSubject = `Denker Feedback: ${feedbackType.charAt(0).toUpperCase() + feedbackType.slice(1)} - ${title}`;
      const emailBody = `
Feedback Type: ${feedbackType.charAt(0).toUpperCase() + feedbackType.slice(1)}
Title: ${title}

Description:
${description}

---
Sent from Denker App
      `.trim();
      
      // Create mailto URL
      const mailtoUrl = `mailto:info@denker.ai?subject=${encodeURIComponent(emailSubject)}&body=${encodeURIComponent(emailBody)}`;
      
      // Try to open with Electron shell first, then fallback to window.open
      // @ts-ignore
      if (window.electron?.shell?.openExternal) {
        // @ts-ignore
        await window.electron.shell.openExternal(mailtoUrl);
      } else {
        window.open(mailtoUrl, '_self');
      }
      
      setAlert({
        open: true,
        message: 'Email client opened! Please send the email to complete your feedback submission.',
        severity: 'success',
      });
      
      // Reset form after successful email opening
      setTimeout(() => {
        setFeedbackType('general');
        setTitle('');
        setDescription('');
      }, 1000);
      
    } catch (error) {
      setAlert({
        open: true,
        message: 'Failed to open email client. Please try again or email info@denker.ai directly.',
        severity: 'error',
      });
    } finally {
      setIsSubmitting(false);
    }
  };
  
  // Go back to main window
  const handleBack = () => {
    navigate('/');
  };
  
  // Close alert
  const handleCloseAlert = () => {
    setAlert({ ...alert, open: false });
  };
  
  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        height: '100vh',
        width: '100%',
        overflow: 'hidden',
        backgroundColor: theme.palette.background.default,
        p: 3,
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', mb: 3 }}>
        <IconButton onClick={handleBack} sx={{ mr: 2 }}>
          <ArrowBackIcon />
        </IconButton>
        <Typography variant="h5" component="h1">
          Feedback
        </Typography>
      </Box>
      
      <Paper
        elevation={0}
        sx={{
          p: 3,
          backgroundColor: 'rgba(30, 30, 30, 0.6)',
          backdropFilter: 'blur(10px)',
          border: '1px solid rgba(255, 255, 255, 0.1)',
          borderRadius: 2,
          flexGrow: 1,
          overflow: 'auto',
        }}
      >
        <Typography variant="body2" paragraph>
          We value your feedback! Please let us know about any bugs, feature requests, or general feedback you have about Denker. Clicking "Send via Email" will open your default email client with a pre-filled message to info@denker.ai.
        </Typography>
        
        <Box component="form" onSubmit={handleSubmit} noValidate sx={{ mt: 3 }}>
          <FormControl component="fieldset" sx={{ mb: 3 }}>
            <Typography variant="body2" gutterBottom sx={{ fontWeight: 600 }}>
              Feedback Type*
            </Typography>
            <RadioGroup
              row
              name="feedback-type"
              value={feedbackType}
              onChange={(e) => setFeedbackType(e.target.value as FeedbackType)}
            >
              <FormControlLabel value="bug" control={<Radio />} label="Bug Report" />
              <FormControlLabel value="feature" control={<Radio />} label="Feature Request" />
              <FormControlLabel value="general" control={<Radio />} label="General Feedback" />
            </RadioGroup>
          </FormControl>
          
          <TextField
            margin="normal"
            required
            fullWidth
            id="title"
            label="Title"
            name="title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            variant="outlined"
            sx={{ mb: 3 }}
          />
          
          <TextField
            margin="normal"
            required
            fullWidth
            id="description"
            label="Description"
            name="description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            variant="outlined"
            multiline
            rows={6}
            sx={{ mb: 3 }}
          />
          

          
          <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 2 }}>
            <Button
              variant="outlined"
              onClick={handleBack}
              sx={{ mr: 2 }}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="contained"
              color="primary"
              disabled={isSubmitting}
              startIcon={isSubmitting ? <CircularProgress size={20} /> : null}
            >
              Send via Email
            </Button>
          </Box>
        </Box>

        {/* Meeting arrangement section - moved below submit button */}
        <Box sx={{ mt: 3, p: 2, backgroundColor: 'rgba(25, 118, 210, 0.08)', borderRadius: 1, border: '1px solid rgba(25, 118, 210, 0.2)' }}>
            <Box>
            <Typography variant="body1" gutterBottom sx={{ fontWeight: 600 }}>
                Arrange a meeting with us
              </Typography>
            <Typography variant="body2" sx={{ mb: 2 }}>
                Want to discuss your feedback in person?
              </Typography>
            <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
            <Button
              variant="outlined"
              color="primary"
              component="a"
              href="https://calendar.notion.so/meet/juanzhang/denkerfeedback"
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => {
                e.preventDefault();
                // @ts-ignore
                if (window.electron?.shell?.openExternal) {
                  // @ts-ignore
                  window.electron.shell.openExternal('https://calendar.notion.so/meet/juanzhang/denkerfeedback');
                } else {
                  window.open('https://calendar.notion.so/meet/juanzhang/denkerfeedback', '_blank', 'noopener,noreferrer');
                }
              }}
                sx={{ textTransform: 'none' }}
            >
              Schedule Meeting
            </Button>
            </Box>
          </Box>
        </Box>
      </Paper>
      
      <Snackbar
        open={alert.open}
        autoHideDuration={6000}
        onClose={handleCloseAlert}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert onClose={handleCloseAlert} severity={alert.severity}>
          {alert.message}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default FeedbackPage; 