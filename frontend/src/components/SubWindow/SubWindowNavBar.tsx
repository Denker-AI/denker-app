import React from 'react';
import { 
  AppBar, 
  Toolbar, 
  Typography, 
  IconButton, 
  Box 
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';

interface SubWindowNavBarProps {
  selectedText?: string;
  onClose: () => void;
  onOpenMainWindow: () => void;
}

const SubWindowNavBar: React.FC<SubWindowNavBarProps> = ({ 
  selectedText, 
  onClose,
  onOpenMainWindow
}) => {
  const handleOpenMainWindow = () => {
    onClose(); // Close the subwindow first
    onOpenMainWindow(); // Then open the main window
  };

  return (
    <AppBar 
      position="static" 
      color="transparent" 
      elevation={0}
      sx={{ 
        backgroundColor: 'rgba(18, 18, 18, 0.8)',
        backdropFilter: 'blur(10px)',
        borderBottom: '1px solid rgba(255, 255, 255, 0.1)',
        WebkitAppRegion: 'drag', // Make the NavBar draggable
      }}
    >
      <Toolbar variant="dense" sx={{ minHeight: 48 }}>
        <IconButton 
          size="small" 
          edge="start" 
          color="inherit" 
          onClick={onClose}
          sx={{ mr: 2, WebkitAppRegion: 'no-drag' }} // Make the button not draggable
        >
          <CloseIcon fontSize="small" />
        </IconButton>
        
        <Typography 
          variant="subtitle2" 
          component="div" 
          sx={{ 
            flexGrow: 1,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {selectedText ? `"${selectedText.substring(0, 50)}${selectedText.length > 50 ? '...' : ''}"` : 'Denker'}
        </Typography>
        
        <IconButton 
          size="small" 
          edge="end" 
          color="inherit" 
          onClick={handleOpenMainWindow}
          sx={{ WebkitAppRegion: 'no-drag' }} // Make the button not draggable
        >
          <ArrowForwardIcon fontSize="small" />
        </IconButton>
      </Toolbar>
    </AppBar>
  );
};

export default SubWindowNavBar; 