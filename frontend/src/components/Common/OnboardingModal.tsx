import React, { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
  Box,
  Stepper,
  Step,
  StepLabel,
  IconButton,
  useTheme,
  Paper,
  Snackbar,
  Alert
} from '@mui/material';
import { 
  Close as CloseIcon, 
  NavigateBefore, 
  NavigateNext,
  Settings as SettingsIcon,
  FolderOpen as FolderIcon,
  QuestionMark as HelpIcon,
  AccountCircle as ProfileIcon,
  Screenshot as ScreenshotIcon,
  Keyboard as KeyboardIcon,
  ContentCopy as CopyIcon,
  Add as AddIcon
} from '@mui/icons-material';

interface OnboardingModalProps {
  open: boolean;
  onClose: () => void;
}

interface Step {
  title: string;
  content: string | React.ReactNode;
}

const OnboardingModal: React.FC<OnboardingModalProps> = ({ open, onClose }) => {
  const [activeStep, setActiveStep] = useState(0);
  const [copySuccess, setCopySuccess] = useState(false);
  const theme = useTheme();

  const demoRequest = `Search online for the latest German population data and create a 2-page report with charts and tables. Include current population statistics, demographic trends, age distribution, and regional breakdowns. Show me a preview of the report when done.`;

  const handleCopyDemo = async () => {
    try {
      await navigator.clipboard.writeText(demoRequest);
      setCopySuccess(true);
    } catch (err) {
      console.error('Failed to copy text: ', err);
    }
  };

  const triggerScreenshotPermission = () => {
    // Trigger the shortcut to show permission dialog
    if (window.electron && (window.electron as any).triggerScreenshotPermission) {
      (window.electron as any).triggerScreenshotPermission();
    } else {
      // Fallback: show instruction to user
      alert('Please press ⌘ + Shift + D to test the screenshot permission!');
    }
  };

  const steps: Step[] = [
    {
      title: "🎉 Welcome to Denker!",
      content: (
        <Box>
          <Typography variant="body1" sx={{ mb: 2 }}>
            Welcome to your new <strong>AI-powered workspace</strong>! With Denker, you now have access to multiple intelligent agents that can:
          </Typography>
          <Box component="ul" sx={{ pl: 2, mb: 0 }}>
            <li><strong>Research</strong> any topic instantly</li>
            <li><strong>Write and edit</strong> files in any format</li>
            <li><strong>Complete complex tasks</strong> with automated plans</li>
            <li><strong>Understand context</strong> from your screen</li>
          </Box>
        </Box>
      )
    },
    {
      title: "📸 Enable Screenshot Context",
      content: (
        <Box>
          <Typography variant="body1" sx={{ mb: 2 }}>
            For the <strong>best AI assistance</strong>, Denker needs permission to take screenshots to understand your context.
          </Typography>
          <Typography variant="body1" sx={{ mb: 2 }}>
            <strong>Try it now:</strong> First copy some text with 
            <Box component="kbd" sx={{ 
              bgcolor: 'grey.200', 
              color: 'grey.800', 
              px: 1, 
              py: 0.5, 
              borderRadius: 1,
              fontFamily: 'monospace',
              fontSize: '0.85em',
              mx: 0.5,
              display: 'inline-block',
              whiteSpace: 'nowrap'
            }}>
              ⌘ + C
            </Box>, then press 
            <Box component="kbd" sx={{ 
              bgcolor: 'grey.200', 
              color: 'grey.800', 
              px: 1, 
              py: 0.5, 
              borderRadius: 1,
              fontFamily: 'monospace',
              fontSize: '0.85em',
              mx: 0.5,
              display: 'inline-block',
              whiteSpace: 'nowrap'
            }}>
              ⌘ + Shift + D
            </Box> to trigger the permission dialog.
          </Typography>
          <Button
            variant="outlined"
            startIcon={<ScreenshotIcon />}
            onClick={triggerScreenshotPermission}
            sx={{ mt: 1 }}
          >
            Test Screenshot Permission
          </Button>
          <Typography variant="body2" sx={{ mt: 2, fontStyle: 'italic' }}>
            After granting permission, you can select any text on your screen, copy it, and press the shortcut to get instant AI assistance!
          </Typography>
        </Box>
      )
    },
    {
      title: "📁 Setup File Delivery",
      content: (
        <Box>
          <Typography variant="body1" sx={{ mb: 2 }}>
            Denker creates files in a <strong>temporary workspace</strong> by default. To save files directly to your preferred location:
          </Typography>
          <Typography variant="body1" sx={{ mb: 2 }}>
            1. Go to <SettingsIcon sx={{ fontSize: 16, mx: 0.5 }} /> <strong>Settings</strong> (in the side menu)
          </Typography>
          <Typography variant="body1" sx={{ mb: 2 }}>
            2. Add a <FolderIcon sx={{ fontSize: 16, mx: 0.5 }} /> <strong>delivery folder</strong>
          </Typography>
          <Typography variant="body1" sx={{ mb: 2 }}>
            <strong>Popular choices:</strong>
          </Typography>
          <Box component="ul" sx={{ pl: 2, mb: 0 }}>
            <li>📥 <u>Downloads folder</u> - for easy access</li>
            <li>🖥️ <u>Desktop</u> - for immediate visibility</li>
            <li>📂 <u>Projects folder</u> - for organized work</li>
          </Box>
        </Box>
      )
    },
    {
      title: "💭 We Value Your Feedback",
      content: (
        <Box>
          <Typography variant="body1" sx={{ mb: 2 }}>
            Denker is currently in <strong>beta testing phase</strong>. Your feedback helps us improve!
          </Typography>
          <Typography variant="body1" sx={{ mb: 2 }}>
            Share your thoughts by clicking the <HelpIcon sx={{ fontSize: 16, mx: 0.5 }} /> <strong>help icon</strong> in the side menu.
          </Typography>
          <Typography variant="body2" sx={{ fontStyle: 'italic', color: 'text.secondary' }}>
            Found a bug? Have a feature request? We'd love to hear from you!
          </Typography>
        </Box>
      )
    },
    {
      title: "👤 Your Account & Support",
      content: (
        <Box>
          <Typography variant="body1" sx={{ mb: 2 }}>
            Your <ProfileIcon sx={{ fontSize: 16, mx: 0.5 }} /> <strong>profile</strong> is accessible from the side menu, where you can:
          </Typography>
          <Box component="ul" sx={{ pl: 2, mb: 2 }}>
            <li>View your <strong>free account</strong> status</li>
            <li>Track usage and features</li>
            <li>Upgrade for additional capabilities</li>
          </Box>
          <Typography variant="body1" sx={{ mb: 2 }}>
            <strong>Support Denker:</strong> Consider upgrading to help us deliver better features faster and keep improving your AI experience!
          </Typography>
          <Typography variant="body2" sx={{ fontStyle: 'italic', color: 'primary.main' }}>
            Thank you for being part of our journey! 🚀
          </Typography>
        </Box>
      )
    },
    {
      title: "🚀 Try Denker Now!",
      content: (
        <Box>
          <Typography variant="body1" sx={{ mb: 2 }}>
            Ready to see Denker in action? Let's create your first conversation and give Denker a task to complete!
          </Typography>
          <Typography variant="body1" sx={{ mb: 2 }}>
            <strong>Here's a demo request to try:</strong>
          </Typography>
          <Paper 
            sx={{ 
              p: 2, 
              bgcolor: 'grey.800', 
              color: 'grey.100',
              border: 1, 
              borderColor: 'grey.600',
              mb: 2,
              position: 'relative'
            }}
          >
            <Typography variant="body2" sx={{ fontFamily: 'monospace', lineHeight: 1.5, color: 'inherit' }}>
              {demoRequest}
            </Typography>
            <Button
              size="small"
              startIcon={<CopyIcon />}
              onClick={handleCopyDemo}
              sx={{ 
                position: 'absolute', 
                top: 8, 
                right: 8,
                bgcolor: 'grey.700',
                color: 'grey.100',
                '&:hover': {
                  bgcolor: 'grey.600'
                }
              }}
            >
              Copy
            </Button>
          </Paper>
          <Typography variant="body1" sx={{ mb: 2 }}>
            <strong>To test this:</strong>
          </Typography>
          <Box component="ol" sx={{ pl: 2, mb: 2 }}>
            <li>Click <strong>"Get Started"</strong> to close this dialog</li>
            <li>Click <AddIcon sx={{ fontSize: 16, mx: 0.5 }} /> <strong>"New Conversation"</strong> in the side menu</li>
            <li>Paste the demo request above and press Enter</li>
                         <li>Watch Denker research data and create a report with charts!</li>
          </Box>
                     <Typography variant="body2" sx={{ fontStyle: 'italic', color: 'primary.main' }}>
             This demo showcases Denker's ability to search online, analyze data, and create reports with visualizations automatically.
          </Typography>
        </Box>
      )
    }
  ];

  const handleNext = () => {
    setActiveStep((prevStep) => prevStep + 1);
  };

  const handleBack = () => {
    setActiveStep((prevStep) => prevStep - 1);
  };

  const handleFinish = () => {
    onClose();
  };

  const isLastStep = activeStep === steps.length - 1;

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="md"
      fullWidth
      PaperProps={{
        sx: {
          borderRadius: 2,
          maxHeight: '80vh'
        }
      }}
    >
      <DialogTitle
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          borderBottom: `1px solid ${theme.palette.divider}`,
          pb: 2
        }}
      >
        <Typography variant="h5" component="div" sx={{ fontWeight: 600 }}>
          Getting Started with Denker
        </Typography>
        <IconButton onClick={onClose} size="small">
          <CloseIcon />
        </IconButton>
      </DialogTitle>

      <DialogContent sx={{ pt: 3 }}>
        <Box sx={{ width: '100%', mb: 3 }}>
          <Stepper activeStep={activeStep} alternativeLabel>
            {steps.map((step, index) => (
              <Step key={index}>
                <StepLabel>{`Step ${index + 1}`}</StepLabel>
              </Step>
            ))}
          </Stepper>
        </Box>

        <Box sx={{ mt: 4, mb: 3, minHeight: 200 }}>
          <Typography
            variant="h6"
            component="h3"
            sx={{
              mb: 2,
              fontWeight: 600,
              color: theme.palette.primary.main
            }}
          >
            {steps[activeStep].title}
          </Typography>
          <Box
            sx={{
              lineHeight: 1.6,
              fontSize: '1.1rem',
              color: theme.palette.text.primary,
              '& strong': {
                fontWeight: 600,
                color: theme.palette.primary.main
              },
              '& u': {
                textDecoration: 'underline',
                textDecorationColor: theme.palette.primary.main
              }
            }}
          >
            {typeof steps[activeStep].content === 'string' ? (
              <Typography variant="body1">
                {steps[activeStep].content}
              </Typography>
            ) : (
              steps[activeStep].content
            )}
          </Box>
        </Box>
      </DialogContent>

      <DialogActions
        sx={{
          justifyContent: 'space-between',
          px: 3,
          pb: 3,
          borderTop: `1px solid ${theme.palette.divider}`,
          pt: 2
        }}
      >
        <Button
          onClick={handleBack}
          disabled={activeStep === 0}
          startIcon={<NavigateBefore />}
          variant="outlined"
        >
          Previous
        </Button>

        <Typography variant="body2" color="text.secondary">
          {activeStep + 1} of {steps.length}
        </Typography>

        {isLastStep ? (
          <Button
            onClick={handleFinish}
            variant="contained"
            color="primary"
            sx={{ px: 3 }}
          >
            Get Started
          </Button>
        ) : (
          <Button
            onClick={handleNext}
            variant="contained"
            endIcon={<NavigateNext />}
            sx={{ px: 3 }}
          >
            Next
          </Button>
        )}
      </DialogActions>

      <Snackbar
        open={copySuccess}
        autoHideDuration={2000}
        onClose={() => setCopySuccess(false)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert 
          onClose={() => setCopySuccess(false)} 
          severity="success" 
          sx={{ width: '100%' }}
        >
          Demo request copied to clipboard!
        </Alert>
      </Snackbar>
    </Dialog>
  );
};

export default OnboardingModal; 