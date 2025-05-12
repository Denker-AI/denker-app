import React from 'react';
import {
  AppBar,
  Toolbar,
  IconButton,
  Typography,
  Box,
  useTheme,
  Tooltip,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import RefreshIcon from '@mui/icons-material/Refresh';
import { useAuth0 } from '@auth0/auth0-react';

interface LoginNavBarProps {
  onReload?: () => void;
}

/**
 * LoginNavBar component for the login page header
 * 
 * Provides window controls and authentication status
 */
const LoginNavBar: React.FC<LoginNavBarProps> = ({ onReload }) => {
  const { isLoading, isAuthenticated } = useAuth0();
  const theme = useTheme();

  // Handle window minimize
  const handleMinimize = () => {
    if (window.electron) {
      window.electron.minimizeMainWindow();
    }
  };
  
  // Handle reload
  const handleReload = () => {
    if (onReload) {
      onReload();
    } else {
      window.location.reload();
    }
  };

  // Determine status text
  const getStatusText = () => {
    if (isLoading) return "Logging in...";
    if (isAuthenticated) return "Logged in";
    return "Please sign in";
  };

  // Determine status color
  const getStatusColor = () => {
    if (isLoading) return theme.palette.warning.main; // Amber/orange for loading
    if (isAuthenticated) return theme.palette.success.main; // Green for success
    return theme.palette.mode === 'dark' 
      ? theme.palette.primary.main 
      : theme.palette.primary.dark; // Default color
  };

  return (
    <AppBar 
      position="static" 
      color="transparent" 
      elevation={0}
      sx={{
        backgroundColor: theme.palette.mode === 'dark' 
          ? 'rgba(18, 18, 18, 0.8)'
          : 'rgba(255, 255, 255, 0.8)',
        borderBottom: `1px solid ${theme.palette.divider}`,
        backdropFilter: 'blur(10px)',
        WebkitAppRegion: 'drag',
        height: 48,
        '& .MuiToolbar-root': {
          height: 48,
          minHeight: 48,
        }
      }}
    >
      <Toolbar variant="dense" sx={{ minHeight: 48 }}>
        <Tooltip title="Minimize">
          <IconButton
            edge="start"
            color="inherit"
            aria-label="minimize"
            onClick={handleMinimize}
            size="small"
            sx={{ mr: 1, WebkitAppRegion: 'no-drag' }} // Make the button not draggable
          >
            <CloseIcon fontSize="small" />
          </IconButton>
        </Tooltip>
        
        <Tooltip title="Reload">
          <IconButton
            color="inherit"
            aria-label="reload"
            onClick={handleReload}
            size="small"
            sx={{ mr: 2, WebkitAppRegion: 'no-drag' }} // Make the button not draggable
          >
            <RefreshIcon fontSize="small" />
          </IconButton>
        </Tooltip>

        <Typography
          variant="subtitle1"
          component="div"
          sx={{ 
            flexGrow: 1, 
            fontWeight: 500,
            color: getStatusColor(),
            textAlign: 'center',
          }}
        >
          {getStatusText()}
        </Typography>

        <Box sx={{ width: 48 }} /> {/* Empty space to balance the layout */}
      </Toolbar>
    </AppBar>
  );
};

export default LoginNavBar; 