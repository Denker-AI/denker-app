import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  Typography,
  Stepper,
  Step,
  StepLabel,
  StepContent,
  Paper,
  IconButton,
  useTheme,
  useMediaQuery,
  Avatar,
  Fade,
  Slide
} from '@mui/material';
import {
  Close as CloseIcon,
  Menu as MenuIcon,
  Settings as SettingsIcon,
  Feedback as FeedbackIcon,
  FolderOpen as FolderIcon,
  Chat as ChatIcon,
  Lightbulb as LightbulbIcon,
  ArrowForward as ArrowForwardIcon,
  CheckCircle as CheckCircleIcon
} from '@mui/icons-material';

interface OnboardingGuideProps {
  open: boolean;
  onClose: () => void;
  onSkip: () => void;
}

interface OnboardingStep {
  id: string;
  title: string;
  description: string;
  icon: React.ReactNode;
  actionText?: string;
  highlight?: string;
}

const onboardingSteps: OnboardingStep[] = [
  {
    id: 'welcome',
    title: 'Welcome to Denker!',
    description: 'Your intelligent AI assistant is ready to help you be more productive. Let\'s get you started with a quick tour.',
    icon: <LightbulbIcon sx={{ fontSize: 40, color: '#1976d2' }} />,
    actionText: 'Get Started'
  },
  {
    id: 'sidemenu',
    title: 'Explore the Side Menu',
    description: 'Click the menu icon (☰) in the top-left corner to access conversations, files, settings, and more. This is your command center!',
    icon: <MenuIcon sx={{ fontSize: 40, color: '#1976d2' }} />,
    highlight: 'side menu',
    actionText: 'Got It'
  },
  {
    id: 'settings',
    title: 'Set Up Accessible Folders',
    description: 'Go to Settings to add folders that Denker can access. This allows your AI assistant to help with your files and projects.',
    icon: <SettingsIcon sx={{ fontSize: 40, color: '#1976d2' }} />,
    highlight: 'Settings',
    actionText: 'Understood'
  },
  {
    id: 'folders',
    title: 'Add Your Folders',
    description: 'In Settings, use "Add Accessible Folder" to grant Denker access to your project directories. The more access you provide, the more helpful Denker becomes!',
    icon: <FolderIcon sx={{ fontSize: 40, color: '#1976d2' }} />,
    highlight: 'accessible folders',
    actionText: 'Makes Sense'
  },
  {
    id: 'chat',
    title: 'Start Chatting',
    description: 'Once set up, start chatting with Denker! Ask questions about your code, request file modifications, or get help with any task.',
    icon: <ChatIcon sx={{ fontSize: 40, color: '#1976d2' }} />,
    actionText: 'Ready to Chat'
  },
  {
    id: 'feedback',
    title: 'Share Your Feedback',
    description: 'Found something helpful or need improvement? Use the Feedback option in the side menu to help us make Denker even better!',
    icon: <FeedbackIcon sx={{ fontSize: 40, color: '#1976d2' }} />,
    highlight: 'Feedback',
    actionText: 'Will Do'
  }
];

const OnboardingGuide: React.FC<OnboardingGuideProps> = ({ open, onClose, onSkip }) => {
  const [activeStep, setActiveStep] = useState(0);
  const [completed, setCompleted] = useState<Set<number>>(new Set());
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));

  console.log('[OnboardingGuide] Component rendered with open:', open);

  const handleComplete = () => {
    // Mark onboarding as completed in localStorage
    localStorage.setItem('denker_onboarding_completed', 'true');
    localStorage.setItem('denker_onboarding_completed_date', new Date().toISOString());
    onClose();
  };

  const handleNext = () => {
    setCompleted(prev => new Set(prev.add(activeStep)));
    if (activeStep < onboardingSteps.length - 1) {
      setActiveStep(prev => prev + 1);
    } else {
      handleComplete();
    }
  };

  // Auto-advance welcome step after a moment
  useEffect(() => {
    if (open && activeStep === 0) {
      const timer = setTimeout(() => {
        handleNext();
      }, 3000);
      return () => clearTimeout(timer);
    }
  }, [open, activeStep]);

  const handleBack = () => {
    if (activeStep > 0) {
      setActiveStep(prev => prev - 1);
    }
  };

  const handleStepClick = (stepIndex: number) => {
    setActiveStep(stepIndex);
  };

  const handleSkipAll = () => {
    localStorage.setItem('denker_onboarding_skipped', 'true');
    localStorage.setItem('denker_onboarding_skipped_date', new Date().toISOString());
    onSkip();
  };

  const currentStep = onboardingSteps[activeStep];
  const isLastStep = activeStep === onboardingSteps.length - 1;

  return (
    <Dialog
      open={open}
      onClose={handleSkipAll}
      maxWidth="md"
      fullWidth
      fullScreen={isMobile}
      PaperProps={{
        sx: {
          borderRadius: isMobile ? 0 : 2,
          maxHeight: '90vh',
          backgroundColor: theme.palette.background.paper,
          color: theme.palette.text.primary,
        }
      }}
    >
      <DialogTitle sx={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'center',
        pb: 1,
        backgroundColor: 'transparent'
      }}>
        <Box display="flex" alignItems="center" gap={2}>
          <Avatar sx={{ bgcolor: theme.palette.primary.main, width: 40, height: 40 }}>
            <LightbulbIcon />
          </Avatar>
          <Typography variant="h5" component="div" fontWeight="bold">
            Getting Started Guide
          </Typography>
        </Box>
        <IconButton onClick={handleSkipAll} size="small">
          <CloseIcon />
        </IconButton>
      </DialogTitle>

      <DialogContent sx={{ pt: 1 }}>
        <Box sx={{ mb: 3 }}>
          <Stepper activeStep={activeStep} orientation={isMobile ? 'vertical' : 'horizontal'}>
            {onboardingSteps.map((step, index) => (
              <Step key={step.id} completed={completed.has(index)}>
                <StepLabel 
                  onClick={() => handleStepClick(index)}
                  sx={{ cursor: 'pointer' }}
                >
                  {isMobile ? step.title : ''}
                </StepLabel>
                {isMobile && (
                  <StepContent>
                    <Paper
                      elevation={3}
                                             sx={{
                         p: 3,
                         mt: 2,
                         backgroundColor: theme.palette.background.default,
                         border: `1px solid ${theme.palette.divider}`,
                       }}
                    >
                      <Fade in={activeStep === index} timeout={500}>
                        <Box textAlign="center">
                          <Box mb={2}>
                            {step.icon}
                          </Box>
                          <Typography variant="h6" gutterBottom fontWeight="bold">
                            {step.title}
                          </Typography>
                          <Typography variant="body1" color="text.secondary" sx={{ mb: 2 }}>
                            {step.description}
                          </Typography>
                          {step.highlight && (
                                                         <Typography 
                               variant="body2" 
                               sx={{ 
                                 fontWeight: 'bold',
                                 color: theme.palette.primary.main,
                                 backgroundColor: theme.palette.primary.main + '20', // 20% opacity
                                 padding: '4px 8px',
                                 borderRadius: 1,
                                 display: 'inline-block',
                                 mb: 2
                               }}
                             >
                              💡 Look for: {step.highlight}
                            </Typography>
                          )}
                        </Box>
                      </Fade>
                    </Paper>
                  </StepContent>
                )}
              </Step>
            ))}
          </Stepper>
        </Box>

        {!isMobile && (
          <Slide direction="up" in={true} timeout={500}>
            <Paper
              elevation={6}
                             sx={{
                 p: 4,
                 textAlign: 'center',
                 backgroundColor: theme.palette.background.default,
                 border: `1px solid ${theme.palette.divider}`,
                 borderRadius: 3,
                 minHeight: 250,
                 display: 'flex',
                 flexDirection: 'column',
                 justifyContent: 'center'
               }}
            >
              <Fade in={true} timeout={800}>
                <Box>
                  <Box mb={3}>
                    {currentStep.icon}
                  </Box>
                  <Typography variant="h4" gutterBottom fontWeight="bold" color="primary">
                    {currentStep.title}
                  </Typography>
                  <Typography variant="body1" color="text.secondary" sx={{ mb: 3, fontSize: '1.1rem', lineHeight: 1.6 }}>
                    {currentStep.description}
                  </Typography>
                  {currentStep.highlight && (
                    <Box sx={{ mb: 3 }}>
                                             <Typography 
                         variant="body1" 
                         sx={{ 
                           fontWeight: 'bold',
                           color: theme.palette.primary.main,
                           backgroundColor: theme.palette.primary.main + '20', // 20% opacity
                           padding: '8px 16px',
                           borderRadius: 2,
                           display: 'inline-block',
                           fontSize: '1rem'
                         }}
                       >
                        💡 Look for: {currentStep.highlight}
                      </Typography>
                    </Box>
                  )}
                </Box>
              </Fade>
            </Paper>
          </Slide>
        )}
      </DialogContent>

      <DialogActions sx={{ p: 3, backgroundColor: 'transparent', justifyContent: 'space-between' }}>
        <Button 
          onClick={handleSkipAll} 
          color="inherit"
          size="large"
        >
          Skip Tour
        </Button>
        
        <Box display="flex" gap={2}>
          <Button 
            onClick={handleBack}
            disabled={activeStep === 0}
            variant="outlined"
            size="large"
          >
            Back
          </Button>
          <Button 
            onClick={handleNext}
            variant="contained"
            size="large"
            endIcon={isLastStep ? <CheckCircleIcon /> : <ArrowForwardIcon />}
            sx={{ minWidth: 120 }}
          >
            {isLastStep ? 'Complete' : currentStep.actionText || 'Next'}
          </Button>
        </Box>
      </DialogActions>
    </Dialog>
  );
};

export default OnboardingGuide; 