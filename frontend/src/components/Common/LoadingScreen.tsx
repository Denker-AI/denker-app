import React, { useState, useEffect } from 'react';
import {
  Box,
  CircularProgress,
  Typography,
  useTheme,
  LinearProgress,
} from '@mui/material';
import RocketLaunchIcon from '@mui/icons-material/RocketLaunch';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import IntegrationInstructionsIcon from '@mui/icons-material/IntegrationInstructions';

interface LoadingScreenProps {
  message?: string;
  showDetailedSteps?: boolean;
  duration?: number; // Auto-advance timing in ms
}

const LoadingScreen: React.FC<LoadingScreenProps> = ({
  message = "Loading...", 
  showDetailedSteps = false,
  duration = 5000  // Reduced default from arbitrary to more reasonable 5 seconds
}) => {
  const theme = useTheme();
  const [currentStep, setCurrentStep] = useState(0);
  const [progress, setProgress] = useState(0);
  const [currentTip, setCurrentTip] = useState(0);

  const loadingTips = [
    {
      text: "Select any text on your screen, Cmd + C to copy it, then press Cmd+Shift+D to analyze it!",
      icon: null
    },
    {
      text: "AI agents automatically break down complex tasks into steps, including research, writing, and editing with live preview",
      icon: null
    },
    {
      text: "Create and work with PDFs, Word docs, Excel, images, charts and websites all in one place",
      icon: null
    },
  ];

  const initializationSteps = [
    "Waking up Denker...",
    "Powering up your AI assistant...",
    "Loading your intelligent tools...",
    "Getting everything ready...",
    "Welcome to Denker!"
  ];

  const stepDescriptions = [
    "Starting up your personal AI workspace",
    "Your AI assistant is coming online and learning your preferences",
    "Preparing smart document processing, web search, and analysis tools",
    "Final touches to make everything perfect for you",
    "Ready to boost your productivity!"
  ];

  useEffect(() => {
    if (!showDetailedSteps) return;

    const stepDuration = duration / initializationSteps.length;
    const interval = setInterval(() => {
      setCurrentStep((prev) => {
        if (prev < initializationSteps.length - 1) {
          return prev + 1;
        }
        return prev;
      });
    }, stepDuration);

    return () => clearInterval(interval);
  }, [showDetailedSteps, duration]);

  useEffect(() => {
    if (!showDetailedSteps) return;

    const progressInterval = setInterval(() => {
      setProgress((prev) => {
        if (prev >= 100) return 100;
        return prev + (100 / (duration / 100));
      });
    }, 100);

    return () => clearInterval(progressInterval);
  }, [showDetailedSteps, duration]);

  // Rotate through tips every 4 seconds to show more tips during loading
  useEffect(() => {
    if (!showDetailedSteps) return;

    const tipInterval = setInterval(() => {
      setCurrentTip((prev) => (prev + 1) % loadingTips.length);
    }, 4000);

    return () => clearInterval(tipInterval);
  }, [showDetailedSteps, loadingTips.length]);

  const displayMessage = showDetailedSteps 
    ? initializationSteps[currentStep] 
    : message;

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        minHeight: '100vh',
        backgroundColor: '#000000',
        padding: 3,
        WebkitAppRegion: 'drag', // Make the entire loading screen draggable
        cursor: 'move',
      }}
    >
      {/* Top area - Spacer */}
      <Box sx={{ flex: '0 0 auto', height: '10vh' }} />

      {/* Middle area - Main content with illustration and tips */}
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          flexGrow: 1,
          textAlign: 'center',
          width: '100%',
          maxWidth: 700,
          margin: '0 auto',
        }}
      >
        {/* Beautiful illustration */}
        {showDetailedSteps && (
          <Box
            sx={{
              marginBottom: 4,
              position: 'relative',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            {/* Animated circles background */}
            <Box
              sx={{
                position: 'absolute',
                width: '120px',
                height: '120px',
                borderRadius: '50%',
                background: 'radial-gradient(circle, rgba(100,181,246,0.2) 0%, rgba(100,181,246,0.05) 100%)',
                animation: 'pulse-slow 3s ease-in-out infinite',
                '@keyframes pulse-slow': {
                  '0%': { transform: 'scale(1)', opacity: 0.3 },
                  '50%': { transform: 'scale(1.1)', opacity: 0.5 },
                  '100%': { transform: 'scale(1)', opacity: 0.3 }
                }
              }}
            />
            <Box
              sx={{
                position: 'absolute',
                width: '80px',
                height: '80px',
                borderRadius: '50%',
                background: 'radial-gradient(circle, rgba(129,199,132,0.3) 0%, rgba(129,199,132,0.1) 100%)',
                animation: 'pulse-slow 2s ease-in-out infinite reverse',
              }}
            />
            {/* Main rocket icon */}
            <RocketLaunchIcon
              sx={{
                fontSize: '3rem',
                color: '#ffffff',
                position: 'relative',
                zIndex: 1,
                animation: 'float 2.5s ease-in-out infinite',
                '@keyframes float': {
                  '0%': { transform: 'translateY(0px)' },
                  '50%': { transform: 'translateY(-8px)' },
                  '100%': { transform: 'translateY(0px)' }
                }
              }}
            />
          </Box>
        )}


        
        {!showDetailedSteps && (
          <Typography
            variant="h4"
            sx={{
              color: '#ffffff',
              marginBottom: 3,
              fontWeight: 600,
              fontSize: '1.8rem',
            }}
          >
            {displayMessage}
          </Typography>
        )}

        {/* Tips text - clean and simple */}
        {showDetailedSteps && (
          <Box
            sx={{
              minHeight: '100px',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              width: '100%',
              maxWidth: '600px',
              marginBottom: 4,
              textAlign: 'center',
            }}
          >
            {/* Text */}
            <Typography
              variant="body1"
              sx={{
                color: '#ffffff',
                fontSize: '1.1rem',
                fontWeight: 400,
                textAlign: 'center',
                lineHeight: 1.6,
                letterSpacing: '0.01em',
                opacity: 0.9,
                maxWidth: '500px',
                transition: 'opacity 0.5s ease-in-out',
              }}
            >
              {loadingTips[currentTip].text}
            </Typography>
          </Box>
        )}
      </Box>

      {/* Bottom area - Progress steps, progress bar, and disclaimer - moved higher */}
      {showDetailedSteps && (
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            paddingBottom: 6, // More padding at bottom
            paddingTop: 3, // Move content higher
            minHeight: '140px',
          }}
        >
          {/* Progress step text */}
          <Typography
            variant="body1"
            sx={{
              color: '#ffffff',
              marginBottom: 2,
              fontWeight: 500,
              fontSize: '0.9rem',
              textAlign: 'center',
              background: 'linear-gradient(45deg, #ffffff, #e3f2fd)',
              backgroundClip: 'text',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              animation: 'pulse 1.5s ease-in-out infinite',
              '@keyframes pulse': {
                '0%': { opacity: 0.8 },
                '50%': { opacity: 1 },
                '100%': { opacity: 0.8 }
              }
            }}
          >
            {initializationSteps[currentStep]}
          </Typography>

          <Box sx={{ width: '300px', marginBottom: 3 }}> {/* Narrower progress bar */}
            <LinearProgress 
              variant="determinate" 
              value={progress} 
              sx={{
                height: 8,
                borderRadius: 4,
                backgroundColor: '#333333',
                '& .MuiLinearProgress-bar': {
                  borderRadius: 4,
                  backgroundColor: '#64b5f6',
                },
              }}
            />
            {/* Progress percentage text */}
            <Typography
              variant="caption"
              sx={{
                color: '#aaaaaa',
                fontSize: '0.75rem',
                marginTop: 1,
                display: 'block',
                textAlign: 'center',
                fontWeight: 400,
              }}
            >
              {Math.round(progress)}%
            </Typography>
          </Box>

          {/* Testing phase disclaimer - moved higher */}
          <Box
            sx={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              textAlign: 'center',
              maxWidth: 400, // Narrower disclaimer text
            }}
          >
            <Typography
              variant="body2"
              sx={{
                color: '#ffffff',
                fontSize: '0.8rem',
                fontWeight: 400,
                opacity: 0.7,
                lineHeight: 1.4,
              }}
            >
              Denker is still in testing phase - any feedback is welcomed!
            </Typography>
          </Box>
        </Box>
      )}
    </Box>
  );
};

export default LoadingScreen; 