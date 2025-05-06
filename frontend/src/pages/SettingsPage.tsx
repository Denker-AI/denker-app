import React, { useState } from 'react';
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
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { useNavigate } from 'react-router-dom';

// Hooks
import useUser from '../hooks/useUser';

const SettingsPage: React.FC = () => {
  const theme = useTheme();
  const navigate = useNavigate();
  const { settings, updateUserSettings, isLoading } = useUser();
  
  // Local state for form values
  const [formValues, setFormValues] = useState({
    theme: settings.theme,
    fontSize: settings.fontSize,
    notifications: settings.notifications,
    autoSave: settings.autoSave,
  });
  
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
  
  const handleSwitchChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setFormValues({
      ...formValues,
      [event.target.name]: event.target.checked,
    });
  };
  
  // Save settings
  const handleSave = async () => {
    await updateUserSettings(formValues);
  };
  
  // Go back to main window
  const handleBack = () => {
    navigate('/');
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
        p: 3,
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', mb: 3 }}>
        <IconButton onClick={handleBack} sx={{ mr: 2 }}>
          <ArrowBackIcon />
        </IconButton>
        <Typography variant="h5" component="h1">
          Settings
        </Typography>
      </Box>
      
      <Paper
        elevation={0}
        sx={{
          p: 3,
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
            </Grid>
          </Grid>
          
          {/* Notifications */}
          <Grid item xs={12}>
            <Typography variant="h6" gutterBottom>
              Notifications
            </Typography>
            <Divider sx={{ mb: 2 }} />
            
            <FormGroup>
              <FormControlLabel
                control={
                  <Switch
                    checked={formValues.notifications}
                    onChange={handleSwitchChange}
                    name="notifications"
                    color="primary"
                  />
                }
                label="Enable desktop notifications"
              />
            </FormGroup>
          </Grid>
          
          {/* Behavior */}
          <Grid item xs={12}>
            <Typography variant="h6" gutterBottom>
              Behavior
            </Typography>
            <Divider sx={{ mb: 2 }} />
            
            <FormGroup>
              <FormControlLabel
                control={
                  <Switch
                    checked={formValues.autoSave}
                    onChange={handleSwitchChange}
                    name="autoSave"
                    color="primary"
                  />
                }
                label="Auto-save conversations"
              />
            </FormGroup>
          </Grid>
          
          {/* About */}
          <Grid item xs={12}>
            <Typography variant="h6" gutterBottom>
              About
            </Typography>
            <Divider sx={{ mb: 2 }} />
            
            <Typography variant="body2" paragraph>
              Denker - AI-powered desktop assistant
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Version 0.1.0
            </Typography>
          </Grid>
        </Grid>
      </Paper>
      
      <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 3 }}>
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