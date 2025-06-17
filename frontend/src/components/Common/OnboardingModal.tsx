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
  useTheme
} from '@mui/material';
import { Close as CloseIcon, NavigateBefore, NavigateNext } from '@mui/icons-material';

interface OnboardingModalProps {
  open: boolean;
  onClose: () => void;
}

const OnboardingModal: React.FC<OnboardingModalProps> = ({ open, onClose }) => {
  const [activeStep, setActiveStep] = useState(0);
  const theme = useTheme();

  const steps = [
    {
      title: "Welcome to Denker",
      content: "With Denker now you have multiple agents to help research, write and edit any file in any format, and even complete complex tasks with plans automatically."
    },
    {
      title: "Enable Screenshot Context",
      content: "To enable denker function at it best, you need to first go to settings enable denker to take a screenshot for better context understanding. Then you select any text on your screen, copy it, and press cmd + shift + d to let denker assistant on your current task."
    },
    {
      title: "Setup File Delivery",
      content: "Denker has create a temporary workspace to create and edit files. To enable denker deliver end files to your folder, you need to go to settings (in the side menu) to add a folder to allow denker deliver the file."
    },
    {
      title: "We Value Your Feedback",
      content: "Denker is still in testing phase, give feedback by clicking on the question mark in the side menu."
    },
    {
      title: "Your Account & Support",
      content: "Your profile is in the side menu, you now have a free account to use Denker, you can also support Denker, so that we can deliver better features faster."
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
          <Typography
            variant="body1"
            sx={{
              lineHeight: 1.6,
              fontSize: '1.1rem',
              color: theme.palette.text.primary
            }}
          >
            {steps[activeStep].content}
          </Typography>
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
    </Dialog>
  );
};

export default OnboardingModal; 