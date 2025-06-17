import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  useTheme,
  AppBar,
  Toolbar,
  IconButton,
} from '@mui/material';
import RocketLaunchIcon from '@mui/icons-material/RocketLaunch';
import CloseIcon from '@mui/icons-material/Close';
import RefreshIcon from '@mui/icons-material/Refresh';

interface LoadingScreenProps {
  message?: string;
  showDetailedSteps?: boolean;
  duration?: number; // Auto-advance timing in ms
  progress?: number; // Deprecated - no longer used since progress bar is removed
}

const LoadingScreen: React.FC<LoadingScreenProps> = ({
  message = "Loading...", 
  showDetailedSteps = false,
  duration = 5000,  // Default duration, will be overridden for first-time users
  progress = 0      // Deprecated parameter
}) => {
  const theme = useTheme();
  const [currentTip, setCurrentTip] = useState(0);

  // Check if running in Electron
  const isElectron = window.navigator.userAgent.toLowerCase().indexOf('electron') > -1;

  const handleClose = () => {
    console.log('Close button clicked from LoadingScreen');
    if (isElectron) {
      // In Electron, minimize might be safer than close, depending on main process setup
      (window as any).electron?.minimizeMainWindow?.(); 
    } else {
      // Standard web behavior (might not be applicable if always in Electron)
      window.close(); 
    }
  };

  const handleReload = () => {
    console.log('Reload button clicked from LoadingScreen');
    window.location.reload();
  };

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

  // Rotate through tips every 4 seconds to show more tips during loading
  useEffect(() => {
    if (!showDetailedSteps) return;

    const tipInterval = setInterval(() => {
      setCurrentTip((prev) => (prev + 1) % loadingTips.length);
    }, 4000);

    return () => clearInterval(tipInterval);
  }, [showDetailedSteps, loadingTips.length]);

  const displayMessage = message;

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
      {/* Navigation Bar */}
      <AppBar 
        position="static" 
        color="default" 
        elevation={1}
        sx={{ 
          // Make the AppBar draggable, common for frameless Electron windows
          WebkitAppRegion: 'drag', 
          userSelect: 'none', // Prevent text selection on the draggable region
          backgroundColor: '#000000',
        }}
      >
        <Toolbar variant="dense" sx={{ justifyContent: 'space-between' }}>
          <Box sx={{ 
            // This box will contain buttons, make it non-draggable
            WebkitAppRegion: 'no-drag',
            display: 'flex',
            alignItems: 'center',
          }}>
            <IconButton edge="start" color="inherit" aria-label="reload" onClick={handleReload} sx={{ mr: 1, color: '#ffffff' }}>
              <RefreshIcon />
            </IconButton>
            <IconButton edge="start" color="inherit" aria-label="close" onClick={handleClose} sx={{ color: '#ffffff' }}>
              <CloseIcon />
            </IconButton>
          </Box>
          <Typography variant="subtitle1" sx={{ 
            position: 'absolute', 
            left: '50%', 
            transform: 'translateX(-50%)', 
            WebkitAppRegion: 'no-drag',
            color: '#ffffff'
          }}>
            Welcome to Denker
          </Typography>
          {/* Empty Box to balance the toolbar for space-between */}
          <Box /> 
        </Toolbar>
      </AppBar>

      {/* Main Loading Content */}
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          flexGrow: 1,
          backgroundColor: '#000000',
          padding: 3,
          WebkitAppRegion: 'drag', // Make the main content draggable
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
        {/* Beautiful illustration - always show for visual appeal */}
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

      {/* Bottom area - Progress message and disclaimer */}
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          paddingBottom: 6, // More padding at bottom
          paddingTop: 3, // Move content higher
          minHeight: '100px',
        }}
      >
        {/* Contextual progress message */}
        <Typography
          variant="body1"
          sx={{
            color: '#ffffff',
            marginBottom: 3,
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
          {displayMessage}
        </Typography>

        {/* Testing phase disclaimer */}
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
      </Box>
    </Box>
  );
};

export default LoadingScreen; 