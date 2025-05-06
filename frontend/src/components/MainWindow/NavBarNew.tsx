import React, { useState } from 'react';
import {
  AppBar,
  Toolbar,
  IconButton,
  Typography,
  Box,
  useTheme,
  Tooltip,
} from '@mui/material';
import MenuIcon from '@mui/icons-material/Menu';
import CloseIcon from '@mui/icons-material/Close';
import AddIcon from '@mui/icons-material/Add';
import { useAuth0 } from '@auth0/auth0-react';

interface NavBarProps {
  onToggleSideMenu: () => void;
  title: string;
  onCreateNewConversation?: () => Promise<void>;
}

/**
 * NavBar component for the main window header
 * 
 * Provides app title, window controls, and toggle for the side menu
 */
const NavBarNew: React.FC<NavBarProps> = ({ onToggleSideMenu, title, onCreateNewConversation }) => {
  const { user } = useAuth0();
  const theme = useTheme();
  const [addHover, setAddHover] = useState(false);
  const [menuHover, setMenuHover] = useState(false);

  // Handle window minimize
  const handleMinimize = () => {
    if (window.electron) {
      window.electron.minimizeMainWindow();
    }
  };
  
  // Handle new conversation
  const handleNewConversation = () => {
    if (onCreateNewConversation) {
      onCreateNewConversation();
    }
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
        height: 64,
        '& .MuiToolbar-root': {
          height: 64,
          minHeight: 64,
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

        <Typography
          variant="subtitle1"
          component="div"
          sx={{ 
            flexGrow: 1, 
            fontWeight: 500,
            color: theme.palette.mode === 'dark' 
              ? theme.palette.primary.main 
              : theme.palette.primary.dark,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {title || 'Denker'}
        </Typography>

        <Box sx={{ display: 'flex', alignItems: 'center', WebkitAppRegion: 'no-drag' }}>
          <Tooltip title="New Conversation">
            <IconButton
              color="inherit"
              onClick={handleNewConversation}
              size="small"
              sx={{ 
                mr: 1,
                transition: 'all 0.2s ease-in-out',
                '&:hover': {
                  color: 'primary.main',
                }
              }}
              onMouseEnter={() => setAddHover(true)}
              onMouseLeave={() => setAddHover(false)}
            >
              <AddIcon 
                fontSize="small" 
                sx={{
                  color: addHover ? 'primary.main' : 'inherit',
                }}
              />
            </IconButton>
          </Tooltip>

          <Tooltip title="Toggle Menu">
            <IconButton
              edge="end"
              color="inherit"
              aria-label="menu"
              onClick={onToggleSideMenu}
              size="small"
              sx={{ 
                transition: 'all 0.2s ease-in-out',
                '&:hover': {
                  color: 'primary.main',
                }
              }}
              onMouseEnter={() => setMenuHover(true)}
              onMouseLeave={() => setMenuHover(false)}
            >
              <MenuIcon 
                fontSize="small" 
                sx={{
                  color: menuHover ? 'primary.main' : 'inherit',
                }}
              />
            </IconButton>
          </Tooltip>
        </Box>
      </Toolbar>
    </AppBar>
  );
};

export default NavBarNew; 