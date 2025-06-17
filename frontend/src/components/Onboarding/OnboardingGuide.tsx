import React, { useState, useEffect, useRef } from 'react';
import {
  Box,
  Typography,
  Button,
  Paper,
  IconButton,
  useTheme,
  Fade,
  Dialog,
  DialogContent,
  Backdrop,
  CircularProgress,
} from '@mui/material';
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import CloseIcon from '@mui/icons-material/Close';
import { keyframes } from '@emotion/react';
import useOnboardingStore from '../../store/onboardingStore';

// Arrow animation
const pulseArrow = keyframes`
  0% {
    transform: translateX(0px);
    opacity: 0.8;
  }
  50% {
    transform: translateX(10px);
    opacity: 1;
  }
  100% {
    transform: translateX(0px);
    opacity: 0.8;
  }
`;

const bounceArrow = keyframes`
  0%, 20%, 50%, 80%, 100% {
    transform: translateY(0);
  }
  40% {
    transform: translateY(-10px);
  }
  60% {
    transform: translateY(-5px);
  }
`;

interface OnboardingStep {
  id: number;
  title: string;
  content: string;
  targetSelector?: string;
  arrowDirection?: 'top' | 'bottom' | 'left' | 'right';
  arrowPosition?: { top?: string; bottom?: string; left?: string; right?: string };
  action?: () => void;
  waitForElement?: string;
  skipIfMissing?: boolean;
}

interface OnboardingGuideProps {
  isOpen: boolean;
  onClose: () => void;
  onComplete: () => void;
}

const OnboardingGuide: React.FC<OnboardingGuideProps> = ({ isOpen, onClose, onComplete }) => {
  const theme = useTheme();
  const [currentStep, setCurrentStep] = useState(0);
  const [isWaitingForAction, setIsWaitingForAction] = useState(false);
  const [targetElement, setTargetElement] = useState<HTMLElement | null>(null);
  const observerRef = useRef<MutationObserver | null>(null);
  
  // Get onboarding state to monitor user actions
  const { onboardingData } = useOnboardingStore();

  const steps: OnboardingStep[] = [
    {
      id: 1,
      title: "Welcome to Denker!",
      content: "Welcome to Denker! Here's a quick onboarding guide. Denker has multiple agents to help you research, write, and edit. You can select any text on your screen, copy it (Cmd+C), then press Cmd+Shift+D to wake up Denker for assistance. Let's grant access first - please press Cmd+Shift+D now!",
      waitForElement: 'shortcut-used', // Special case - we'll handle this with state monitoring
    },
    {
      id: 2,
      title: "Open the Menu",
      content: "Great! Now click this hamburger button to check your conversations and file list.",
      targetSelector: 'button[aria-label="menu"]',
      arrowDirection: 'bottom',
      arrowPosition: { top: '20px', right: '20px' },
      waitForElement: '[role="presentation"]', // Drawer element
    },
    {
      id: 3,
      title: "Access Settings",
      content: "Perfect! Now click the settings button to add an accessible folder so Denker can save files directly inside this folder. Tip: A restart is needed for changes to take effect.",
      targetSelector: 'button[title="Settings"]',
      arrowDirection: 'top',
      arrowPosition: { bottom: '20px', left: '20px' },
      skipIfMissing: true,
    },
    {
      id: 4,
      title: "Check Your Profile",
      content: "Now click on your profile section. This is where you can view your account details. You can now use Denker for free!",
      targetSelector: '[role="presentation"] .MuiBox-root:first-child > .MuiBox-root:first-child',
      arrowDirection: 'right',
      arrowPosition: { top: '20px', left: '20px' },
      skipIfMissing: true,
    },
    {
      id: 5,
      title: "Feedback Welcome",
      content: "Finally, here's the feedback button. We encourage you to share your thoughts and help us improve Denker!",
      targetSelector: 'button[title="Help & Feedback"]',
      arrowDirection: 'top',
      arrowPosition: { bottom: '20px', right: '20px' },
      skipIfMissing: true,
    },
    {
      id: 6,
      title: "Try It Out!",
      content: 'Great! Now try creating a new conversation with this input: "Create a pie chart of 80 20 rule, and save the chart with brief intro of the rule and show a live preview to me"',
    },
  ];

  // Find target element for current step
  useEffect(() => {
    if (!isOpen || !steps[currentStep]) return;

    const step = steps[currentStep];
    if (step.targetSelector) {
      const findElement = () => {
        const element = document.querySelector(step.targetSelector!) as HTMLElement;
        if (element) {
          setTargetElement(element);
          return true;
        }
        return false;
      };

      // Try to find immediately
      if (!findElement()) {
        // If not found, set up observer to wait for it
        observerRef.current = new MutationObserver(() => {
          if (findElement()) {
            observerRef.current?.disconnect();
          }
        });

        observerRef.current.observe(document.body, {
          childList: true,
          subtree: true,
        });

        // Timeout after 10 seconds
        setTimeout(() => {
          if (observerRef.current) {
            observerRef.current.disconnect();
            if (step.skipIfMissing) {
              handleNext();
            }
          }
        }, 10000);
      }
    } else {
      setTargetElement(null);
    }

    // Set up waiting for action if waitForElement is specified
    if (step.waitForElement) {
      setIsWaitingForAction(true);
      
      // Handle special cases that don't require DOM monitoring
      if (step.waitForElement === 'shortcut-used') {
        // This will be handled by the auto-advance effect monitoring onboardingData
        return;
      }
      
      // Regular DOM element waiting
      const waitObserver = new MutationObserver(() => {
        const element = document.querySelector(step.waitForElement!);
        if (element) {
          waitObserver.disconnect();
          setIsWaitingForAction(false);
          setTimeout(() => handleNext(), 1000); // Auto-advance after action
        }
      });

      waitObserver.observe(document.body, {
        childList: true,
        subtree: true,
      });

      // Cleanup on step change
      return () => waitObserver.disconnect();
    }
  }, [currentStep, isOpen]);

  // Cleanup observer on unmount
  useEffect(() => {
    return () => {
      observerRef.current?.disconnect();
    };
  }, []);
  
  // Auto-advance based on user actions
  useEffect(() => {
    if (!isOpen) return;
    
    const currentStepData = steps[currentStep];
    if (!currentStepData) return;
    
    // Check if we should auto-advance based on completed actions
    let shouldAdvance = false;
    
    switch (currentStep) {
      case 0: // Welcome step - advance when shortcut is used
        shouldAdvance = onboardingData.hasUsedShortcut;
        break;
      case 1: // Menu step - advance when menu is opened
        shouldAdvance = onboardingData.hasOpenedMenu;
        break;
      case 2: // Settings step - advance when settings are visited
        shouldAdvance = onboardingData.hasVisitedSettings;
        break;
      case 3: // Profile step - advance when profile is viewed
        shouldAdvance = onboardingData.hasViewedProfile;
        break;
      case 4: // Feedback step - advance when feedback is seen
        shouldAdvance = onboardingData.hasSeenFeedback;
        break;
    }
    
    if (shouldAdvance && isWaitingForAction) {
      console.log(`[OnboardingGuide] Auto-advancing from step ${currentStep} due to user action`);
      setTimeout(() => {
        handleNext();
      }, 1000); // Small delay to let user see the completion
    }
  }, [currentStep, onboardingData, isWaitingForAction, isOpen]);

  const handleNext = () => {
    if (currentStep < steps.length - 1) {
      setCurrentStep(currentStep + 1);
      setTargetElement(null);
      setIsWaitingForAction(false);
    } else {
      onComplete();
    }
  };

  const handlePrevious = () => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1);
      setTargetElement(null);
      setIsWaitingForAction(false);
    }
  };

  const handleSkip = () => {
    onComplete();
  };

  if (!isOpen) return null;

  const currentStepData = steps[currentStep];
  const isLastStep = currentStep === steps.length - 1;

  // Get position for the modal
  const getModalPosition = () => {
    if (!targetElement) {
      return {
        position: 'fixed' as const,
        top: '50%',
        left: '50%',
        transform: 'translate(-50%, -50%)',
        zIndex: 9999,
      };
    }

    const rect = targetElement.getBoundingClientRect();
    const windowWidth = window.innerWidth;
    const windowHeight = window.innerHeight;

    // Determine best position based on available space
    let top = rect.bottom + 20;
    let left = rect.left;

    // Adjust if modal would go off screen
    if (top + 300 > windowHeight) {
      top = rect.top - 320;
    }

    if (left + 400 > windowWidth) {
      left = windowWidth - 420;
    }

    if (left < 20) {
      left = 20;
    }

    return {
      position: 'fixed' as const,
      top: `${Math.max(20, top)}px`,
      left: `${left}px`,
      zIndex: 9999,
    };
  };

  // Get arrow position and style
  const getArrowStyle = () => {
    if (!targetElement || !currentStepData.arrowDirection) return null;

    const rect = targetElement.getBoundingClientRect();
    const arrowSize = 40;

    let style: React.CSSProperties = {
      position: 'fixed',
      width: arrowSize,
      height: arrowSize,
      zIndex: 10000,
      color: theme.palette.primary.main,
      filter: 'drop-shadow(0 2px 8px rgba(0,0,0,0.3))',
      animation: `${pulseArrow} 2s ease-in-out infinite`,
    };

    switch (currentStepData.arrowDirection) {
      case 'top':
        style = {
          ...style,
          top: rect.top - arrowSize - 10,
          left: rect.left + rect.width / 2 - arrowSize / 2,
          transform: 'rotate(90deg)',
        };
        break;
      case 'bottom':
        style = {
          ...style,
          top: rect.bottom + 10,
          left: rect.left + rect.width / 2 - arrowSize / 2,
          transform: 'rotate(-90deg)',
        };
        break;
      case 'left':
        style = {
          ...style,
          top: rect.top + rect.height / 2 - arrowSize / 2,
          left: rect.left - arrowSize - 10,
          transform: 'rotate(180deg)',
        };
        break;
      case 'right':
        style = {
          ...style,
          top: rect.top + rect.height / 2 - arrowSize / 2,
          left: rect.right + 10,
          transform: 'rotate(0deg)',
        };
        break;
    }

    return style;
  };

  // Highlight target element
  useEffect(() => {
    if (targetElement) {
      const originalStyle = targetElement.style.cssText;
      targetElement.style.cssText += `
        position: relative !important;
        z-index: 9998 !important;
        box-shadow: 0 0 0 4px ${theme.palette.primary.main}40, 0 0 0 8px ${theme.palette.primary.main}20 !important;
        border-radius: 8px !important;
        animation: ${bounceArrow} 2s ease-in-out infinite !important;
      `;

      return () => {
        targetElement.style.cssText = originalStyle;
      };
    }
  }, [targetElement, theme.palette.primary.main]);

  const arrowStyle = getArrowStyle();

  return (
    <>
      {/* Backdrop */}
      <Backdrop
        open={isOpen}
        sx={{
          zIndex: 9997,
          backgroundColor: 'rgba(0, 0, 0, 0.7)',
          backdropFilter: 'blur(3px)',
        }}
      />

      {/* Arrow pointing to target */}
      {arrowStyle && (
        <ArrowForwardIcon
          sx={arrowStyle}
        />
      )}

      {/* Modal */}
      <Fade in={isOpen}>
        <Paper
          elevation={24}
          sx={{
            ...getModalPosition(),
            width: 400,
            maxWidth: '90vw',
            p: 3,
            backgroundColor: theme.palette.mode === 'dark' 
              ? 'rgba(30, 30, 30, 0.95)' 
              : 'rgba(255, 255, 255, 0.95)',
            backdropFilter: 'blur(10px)',
            border: `2px solid ${theme.palette.primary.main}`,
            borderRadius: 3,
          }}
        >
          {/* Header */}
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            <Typography variant="h6" sx={{ fontWeight: 600, color: theme.palette.primary.main }}>
              Step {currentStep + 1} of {steps.length}
            </Typography>
            <IconButton onClick={onClose} size="small">
              <CloseIcon />
            </IconButton>
          </Box>

          {/* Content */}
          <Typography variant="h6" sx={{ mb: 2, fontWeight: 500 }}>
            {currentStepData.title}
          </Typography>

          <Typography variant="body1" sx={{ mb: 3, lineHeight: 1.6 }}>
            {currentStepData.content}
          </Typography>

          {/* Waiting indicator */}
          {isWaitingForAction && (
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', mb: 2 }}>
              <CircularProgress size={20} sx={{ mr: 1 }} />
              <Typography variant="body2" color="text.secondary">
                Waiting for your action...
              </Typography>
            </Box>
          )}

          {/* Controls */}
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Button
              variant="text"
              onClick={handleSkip}
              sx={{ textTransform: 'none' }}
            >
              Skip Tour
            </Button>

            <Box sx={{ display: 'flex', gap: 1 }}>
              <Button
                variant="outlined"
                onClick={handlePrevious}
                disabled={currentStep === 0}
                startIcon={<ArrowBackIcon />}
                sx={{ textTransform: 'none' }}
              >
                Previous
              </Button>

              <Button
                variant="contained"
                onClick={handleNext}
                disabled={isWaitingForAction}
                endIcon={!isLastStep ? <ArrowForwardIcon /> : null}
                sx={{ textTransform: 'none' }}
              >
                {isLastStep ? 'Finish' : 'Next'}
              </Button>
            </Box>
          </Box>

          {/* Progress indicator */}
          <Box sx={{ mt: 3 }}>
            <Box sx={{ display: 'flex', gap: 1, justifyContent: 'center' }}>
              {steps.map((_, index) => (
                <Box
                  key={index}
                  sx={{
                    width: 8,
                    height: 8,
                    borderRadius: '50%',
                    backgroundColor: index <= currentStep 
                      ? theme.palette.primary.main 
                      : theme.palette.action.disabled,
                    transition: 'all 0.3s ease',
                  }}
                />
              ))}
            </Box>
          </Box>
        </Paper>
      </Fade>
    </>
  );
};

export default OnboardingGuide; 