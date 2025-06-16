/// <reference path="../electron.d.ts" />

import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Divider,
  FormControl,
  FormControlLabel,
  FormGroup,
  Switch,
  Select,
  MenuItem,
  InputLabel,
  Button,
  Paper,
  Grid,
  IconButton,
  useTheme,
  SelectChangeEvent,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import DeleteIcon from '@mui/icons-material/Delete';
import AddCircleOutlineIcon from '@mui/icons-material/AddCircleOutline';
import SystemUpdateAltIcon from '@mui/icons-material/SystemUpdateAlt';
import { useNavigate } from 'react-router-dom';

// Hooks
import useUser from '../hooks/useUser';
// Import api service to call the new local refresh endpoint
import { api } from '../services/api';

// Define available languages - you might want to move this to a config file or constants
const availableLanguages = [
  { value: 'en', label: 'English' },
  { value: 'de', label: 'Deutsch' },
];

const SettingsPage: React.FC = () => {
  const theme = useTheme();
  const navigate = useNavigate();
  const { settings, updateUserSettings, isLoading } = useUser();
  
  // Local state for form values
  const [formValues, setFormValues] = useState({
    theme: settings.theme,
    fontSize: settings.fontSize,
    language: settings.language || 'en',
    accessibleFolders: settings.accessibleFolders || [],
  });
  
  // Sync formValues if settings change (e.g. after initial load)
  useEffect(() => {
    setFormValues({
      theme: settings.theme,
      fontSize: settings.fontSize,
      language: settings.language || 'en',
      accessibleFolders: settings.accessibleFolders || [],
    });
  }, [settings]);
  
  // Handle form changes
  const handleThemeChange = (event: SelectChangeEvent) => {
    setFormValues({
      ...formValues,
      theme: event.target.value as 'light' | 'dark' | 'system',
    });
  };
  
  const handleFontSizeChange = (event: SelectChangeEvent) => {
    setFormValues({
      ...formValues,
      fontSize: event.target.value as 'small' | 'medium' | 'large',
    });
  };

  const handleLanguageChange = (event: SelectChangeEvent) => {
    setFormValues({
      ...formValues,
      language: event.target.value as string,
    });
  };
  
  // Save settings
  const handleSave = async () => {
    console.log('[SettingsPage] handleSave: Clicked');
    const settingsToSave = {
      theme: formValues.theme,
      fontSize: formValues.fontSize,
      language: formValues.language,
      accessibleFolders: formValues.accessibleFolders,
    };
    console.log('[SettingsPage] handleSave: settingsToSave object:', settingsToSave);
    try {
      // Step 1: Save settings to the remote backend
      await updateUserSettings(settingsToSave);
      console.log('[SettingsPage] handleSave: updateUserSettings (to remote) call completed.');

      // Step 2: Notify local backend to refresh its settings cache from remote
      try {
        console.log('[SettingsPage] handleSave: Attempting to call api.refreshLocalSettings()');
        await api.refreshLocalSettings();
        console.log('[SettingsPage] handleSave: api.refreshLocalSettings() call completed.');

        // After all saves are successful, show the restart dialog
        // @ts-ignore
        if (window.electron && window.electron.showRestartDialog) {
          console.log('[SettingsPage] handleSave: Asking user to restart via dialog.');
          // @ts-ignore
          window.electron.showRestartDialog({
            title: 'Settings Updated',
            message: 'Your settings have been successfully saved.',
            detail: 'A restart is recommended for all changes to take full effect, especially for accessible folders and backend configurations.'
          }); // We don't need to await this or handle its response here,
              // as the dialog itself handles the restart action if confirmed.
        } else {
          console.warn('[SettingsPage] handleSave: showRestartDialog function not available on window.electron. Cannot prompt for restart.');
          // Optionally, provide a fallback alert if the dialog isn't available for some reason
          alert("Settings saved. A restart is recommended to apply all changes.");
        }

      } catch (localRefreshError) {
        console.error('[SettingsPage] handleSave: Error calling api.refreshLocalSettings():', localRefreshError);
        // Optionally, inform the user that local settings might be out of sync
        // For now, we just log it. The primary save was to remote.
      }

    } catch (error) {
      console.error('[SettingsPage] handleSave: Error calling updateUserSettings (to remote):', error);
    }
  };
  
  // Go back to main window
  const handleBack = () => {
    navigate('/');
  };
  
  // Accessible Folders handlers
  const handleAddFolder = async () => {
    try {
      // @ts-ignore
      const newFolder = await window.electron.openDirectoryDialog();
      
      if (newFolder && typeof newFolder === 'string') {
        // Check for duplicates before adding
        if (!formValues.accessibleFolders.includes(newFolder)) {
          setFormValues(prev => ({
            ...prev,
            accessibleFolders: [...prev.accessibleFolders, newFolder]
          }));
        } else {
          console.warn('Folder already added:', newFolder);
          // Optionally, show a message to the user (e.g., using a toast notification)
        }
      } else {
        console.log('No folder selected or dialog was canceled.');
      }
    } catch (error) {
      console.error('Error opening folder dialog:', error);
      // Optionally, show an error message to the user
    }
  };

  const handleRemoveFolder = (folderToRemove: string) => {
    setFormValues(prev => ({
      ...prev,
      accessibleFolders: prev.accessibleFolders.filter(folder => folder !== folderToRemove),
    }));
  };
  
  const handleAppRestart = () => {
    console.log('[SettingsPage] Requesting full application restart...');
    // @ts-ignore
    if (window.electron && window.electron.restartApp) {
      // @ts-ignore
      window.electron.restartApp();
    } else {
      console.error('Restart function not available on window.electron');
      alert('App restart functionality is not available.');
    }
  };
  
  const handleCheckForUpdates = () => {
    console.log('Check for updates clicked');
    // Placeholder for update check logic
    // Example: window.electron.checkForUpdates();
    alert('Update check functionality not yet implemented.');
  };
  
  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        height: '100vh',
        width: '100%',
        overflow: 'hidden',
        backgroundColor: theme.palette.background.default,
        // p: 3, // Padding will be applied to inner content Box to allow top bar to be flush for dragging
      }}
    >
      <Box sx={{
        display: 'flex',
        alignItems: 'center',
        p: 3, // Moved padding here from parent
        mb: 0, // Adjusted margin as padding is now on this Box
        // Draggable region styles
        WebkitAppRegion: 'drag', // Make this area draggable
        // Ensure children can override if they are interactive
        '& > *': {
          WebkitAppRegion: 'no-drag', // Default for children, override for specific interactive ones
        },
      }}>
        <IconButton 
          onClick={handleBack} 
          sx={{
             mr: 2,
             WebkitAppRegion: 'no-drag', // Explicitly make button non-draggable
          }}
        >
          <ArrowBackIcon />
        </IconButton>
        <Typography variant="h5" component="h1" sx={{ WebkitAppRegion: 'drag' /* Allow dragging on text if desired, or no-drag */ }}>
          Settings
        </Typography>
      </Box>
      
      <Paper
        elevation={0}
        sx={{
          p: 3, // Keep padding for the content area
          backgroundColor: 'rgba(30, 30, 30, 0.6)',
          backdropFilter: 'blur(10px)',
          border: '1px solid rgba(255, 255, 255, 0.1)',
          borderRadius: 2,
          flexGrow: 1,
          overflow: 'auto',
        }}
      >
        <Grid container spacing={4}>
          {/* Appearance */}
          <Grid item xs={12}>
            <Typography variant="h6" gutterBottom>
              Appearance
            </Typography>
            <Divider sx={{ mb: 2 }} />
            
            <Grid container spacing={3}>
              <Grid item xs={12} sm={6}>
                <FormControl fullWidth variant="outlined" size="small">
                  <InputLabel id="theme-select-label">Theme</InputLabel>
                  <Select
                    labelId="theme-select-label"
                    id="theme-select"
                    value={formValues.theme}
                    onChange={handleThemeChange}
                    label="Theme"
                  >
                    <MenuItem value="light">Light</MenuItem>
                    <MenuItem value="dark">Dark</MenuItem>
                    <MenuItem value="system">System Default</MenuItem>
                  </Select>
                </FormControl>
              </Grid>
              
              <Grid item xs={12} sm={6}>
                <FormControl fullWidth variant="outlined" size="small">
                  <InputLabel id="font-size-select-label">Font Size</InputLabel>
                  <Select
                    labelId="font-size-select-label"
                    id="font-size-select"
                    value={formValues.fontSize}
                    onChange={handleFontSizeChange}
                    label="Font Size"
                  >
                    <MenuItem value="small">Small</MenuItem>
                    <MenuItem value="medium">Medium</MenuItem>
                    <MenuItem value="large">Large</MenuItem>
                  </Select>
                </FormControl>
              </Grid>

              {/* Language Dropdown */}
              <Grid item xs={12} sm={6}>
                <FormControl fullWidth variant="outlined" size="small">
                  <InputLabel id="language-select-label">Language</InputLabel>
                  <Select
                    labelId="language-select-label"
                    id="language-select"
                    value={formValues.language}
                    onChange={handleLanguageChange}
                    label="Language"
                  >
                    {availableLanguages.map((lang) => (
                      <MenuItem key={lang.value} value={lang.value}>
                        {lang.label}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Grid>
            </Grid>
          </Grid>
          
          {/* Accessible Folders - New Section */}
          <Grid item xs={12}>
            <Typography variant="h6" gutterBottom>
              Accessible Folders
            </Typography>
            <Divider sx={{ mb: 2 }} />
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Manage folders that Denker can access for filesystem operations.
            </Typography>
            <List dense>
              {formValues.accessibleFolders.map((folder) => (
                <ListItem key={folder} sx={{ 
                  mb: 1, 
                  backgroundColor: 'rgba(255, 255, 255, 0.05)', 
                  borderRadius: '4px',
                  '&:hover': {
                    backgroundColor: 'rgba(255, 255, 255, 0.08)',
                  }
                }}>
                  <ListItemText primary={folder} primaryTypographyProps={{ style: { overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } }}/>
                  <ListItemSecondaryAction>
                    <IconButton edge="end" aria-label="delete" onClick={() => handleRemoveFolder(folder)} size="small">
                      <DeleteIcon />
                    </IconButton>
                  </ListItemSecondaryAction>
                </ListItem>
              ))}
              {formValues.accessibleFolders.length === 0 && (
                <ListItem>
                  <ListItemText primary="No folders added yet." />
                </ListItem>
              )}
            </List>
            <Button
              variant="outlined"
              startIcon={<AddCircleOutlineIcon />}
              onClick={handleAddFolder}
              sx={{ mt: 2 }}
              size="small"
            >
              Add Folder
            </Button>
          </Grid>
          {/* End Accessible Folders Section */}
          
          {/* About */}
          <Grid item xs={12}>
            <Typography variant="h6" gutterBottom>
              About
            </Typography>
            <Divider sx={{ mb: 2 }} />
            
            <Typography variant="body2" paragraph>
              Denker - AI-powered desktop assistant
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
              Version 0.1.0
            </Typography>
            <Grid container spacing={1}>
              <Grid item xs={12}>
                <Button 
                  variant="outlined" 
                  size="small" 
                  startIcon={<SystemUpdateAltIcon />} 
                  onClick={handleCheckForUpdates}
                  sx={{ mr: 1 }}
                >
                  Check for Updates
                </Button>
                <Button 
                  variant="outlined" 
                  color="warning"
                  size="small" 
                  onClick={handleAppRestart}
                >
                  Restart Application
                </Button>
              </Grid>
            </Grid>
          </Grid>
        </Grid>
      </Paper>
      
      <Box sx={{ display: 'flex', justifyContent: 'flex-end', p: 3 }}>
        <Button
          variant="outlined"
          onClick={handleBack}
          sx={{ mr: 2 }}
        >
          Cancel
        </Button>
        <Button
          variant="contained"
          color="primary"
          onClick={handleSave}
          disabled={isLoading}
        >
          Save Changes
        </Button>
      </Box>
    </Box>
  );
};

export default SettingsPage; 