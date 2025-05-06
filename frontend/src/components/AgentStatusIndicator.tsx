import React, { useState, useEffect, memo } from 'react';
import { Box, Typography, Paper } from '@mui/material'; // Removed CircularProgress
import useAgentStatusStore from '../store/agentStatusStore';
import { 
    Wifi as WifiIcon, 
    PlayArrow as PlayArrowIcon, // Icon for running
    CheckCircle as CheckCircleIcon, // Icon for result
    ErrorOutline as ErrorIcon, // Icon for error
    AltRoute as RoutingIcon, // Icon for Routing
    AccountTree as DecisionIcon, // Icon for Decision
    Person as PersonIcon, // Added Person icon for simple workflow
} from '@mui/icons-material';

// Wrap component definition with memo
const AgentStatusIndicator: React.FC = memo(() => {
  const { statusText, statusType, agentName, workflowType } = useAgentStatusStore();
  const [ellipsis, setEllipsis] = useState('.'); // State for ellipsis animation

  // Re-introduce effect for animating ellipsis
  useEffect(() => {
    let intervalId: NodeJS.Timeout | null = null;
    // Only animate ellipsis when the type is 'Chatting'
    if (statusType === 'Chatting') { 
      intervalId = setInterval(() => {
        setEllipsis((prev) => {
          if (prev === '...') return '.';
          if (prev === '..') return '...';
          return '..';
        });
      }, 500); 
    } else {
      setEllipsis('.'); // Reset ellipsis when status is not Chatting
    }

    return () => {
      if (intervalId) {
        clearInterval(intervalId);
      }
    };
  }, [statusType]); // Rerun effect if statusType changes (to start/stop animation)

  console.log("[AgentStatusIndicator] Rendering. Status Text:", statusText, "Status Type:", statusType, "Agent:", agentName, "Workflow:", workflowType);

  if (!statusText) {
    return null; 
  }

  // Get primary status icon (left side)
  const getStatusIcon = () => {
    const iconStyle = { mr: 0.5, flexShrink: 0, fontSize: '1rem' }; 
    switch (statusType) {
      case 'status': 
        return <WifiIcon sx={iconStyle} />;
      case 'Chatting':
      case 'Routing': // Use Play for Routing as well?
        return <PlayArrowIcon sx={iconStyle} />;
      case 'result':
        return <CheckCircleIcon sx={iconStyle} />;
      case 'error': 
         return <ErrorIcon sx={iconStyle} />;
      default:
        return null; // Don't show icon for decision or unknown types on left
    }
  };

  // Get workflow icon (right side)
  const getWorkflowIcon = () => {
     const iconStyle = { mr: 0.5, flexShrink: 0, fontSize: '1rem' };
     // Add more cases if other workflow types exist
     switch (workflowType?.toLowerCase()) { // Check lowercase for flexibility
         case 'router':
             return <RoutingIcon sx={iconStyle} />;
         case 'orchestrator':
             return <DecisionIcon sx={iconStyle} />;
         case 'simple':
             return <PersonIcon sx={iconStyle} />; // Example icon for simple
         default:
             return null; // No icon if workflowType is null or unknown
     }
  }

  const statusIcon = getStatusIcon();
  const wfIcon = getWorkflowIcon();
  const displayText = statusType === 'Chatting' ? `${statusText}${ellipsis}` : statusText;

  return (
    <Box 
      sx={{
        display: 'flex',
        justifyContent: 'space-between', // Space out left and right elements
        alignItems: 'center', // Align items vertically
        mb: 0, // Remove bottom margin
        px: 2, 
        minHeight: '24px', 
      }}
    >
      {/* Left-aligned Status */}
      <Paper 
        elevation={0} 
        sx={{
          py: 0.5,
          px: statusIcon ? 1.5 : 1, 
          borderRadius: '16px', 
          display: 'inline-flex', 
          alignItems: 'center',
          fontSize: '0.8rem',
          backgroundColor: 'transparent', 
          color: 'text.secondary', 
        }}
      >
        {statusIcon}
        <Typography 
          variant="caption" 
          component="span" 
          sx={{ 
            lineHeight: 1, 
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            color: 'inherit',
          }}
        >
          {displayText}
        </Typography>
      </Paper>

      {/* Right-aligned Workflow Type (only if workflowType exists) */}
      {workflowType && (
        <Paper
          elevation={0}
          sx={{
            py: 0.5,
            px: wfIcon ? 1.5 : 1,
            borderRadius: '16px',
            display: 'inline-flex',
            alignItems: 'center',
            fontSize: '0.8rem',
            backgroundColor: 'transparent',
            color: 'text.secondary',
          }}
        >
           {wfIcon} 
           <Typography
             variant="caption"
             component="span"
             sx={{ 
               lineHeight: 1, 
               whiteSpace: 'nowrap',
               color: 'inherit',
               textTransform: 'capitalize', // Nicely format workflow type
             }}
           >
             {workflowType}
           </Typography>
        </Paper>
      )}
    </Box>
  );
}); // Close memo wrapper

export default AgentStatusIndicator; 