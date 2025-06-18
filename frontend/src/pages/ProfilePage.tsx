import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  TextField,
  Button,
  Paper,
  Avatar,
  IconButton,
  Divider,
  Grid,
  useTheme,
  CircularProgress,
  Alert,
  Tooltip,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import EditIcon from '@mui/icons-material/Edit';
import LogoutIcon from '@mui/icons-material/Logout';
import PhotoCameraIcon from '@mui/icons-material/PhotoCamera';
import { useNavigate } from 'react-router-dom';

import { useAuth } from '../auth/AuthContext';
import useUserPreferences, { UserPreferences } from '../hooks/useUserPreferences';

// Utils
import { stringToColor } from '../utils/helpers';

const ProfilePage: React.FC = () => {
  const theme = useTheme();
  const navigate = useNavigate();
  const { user, logout, isLoading } = useAuth();
  
  // Use custom user preferences hook
  const {
    getDisplayName,
    getAvatarUrl,
    isUsingCustomDisplayName,
    isUsingCustomAvatar,
    saveUserPreferences,
    originalName,
    originalPicture,
    email,
  } = useUserPreferences();
  
  // Local state for form values
  const [formValues, setFormValues] = useState({
    name: '',
    email: '',
    avatarUrl: '',
  });
  
  // Load form values when user or preferences change
  useEffect(() => {
    if (user) {
      setFormValues({
        name: getDisplayName,
        email: email || '',
        avatarUrl: getAvatarUrl,
      });
    }
  }, [user, getDisplayName, getAvatarUrl, email]);

  const [isEditing, setIsEditing] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  
  const handleChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setFormValues({
      ...formValues,
      [event.target.name]: event.target.value,
    });
  };
  
  const handleToggleEdit = () => {
    setIsEditing(!isEditing);
    setSaveSuccess(false);
    
    if (!isEditing) {
      // Entering edit mode - reset form values to current preferences
      setFormValues({
        name: getDisplayName,
        email: email || '',
        avatarUrl: getAvatarUrl,
      });
    }
  };
  
  const handleSave = async () => {
    const newPreferences: UserPreferences = {
      displayName: formValues.name.trim() || undefined,
      avatarUrl: formValues.avatarUrl.trim() || undefined,
    };
    
    // Only save if there are actual changes from Auth0 defaults
    const preferencesToSave: UserPreferences = {};
    if (newPreferences.displayName && newPreferences.displayName !== originalName) {
      preferencesToSave.displayName = newPreferences.displayName;
    }
    if (newPreferences.avatarUrl && newPreferences.avatarUrl !== originalPicture) {
      preferencesToSave.avatarUrl = newPreferences.avatarUrl;
    }
    
    saveUserPreferences(preferencesToSave);
    setIsEditing(false);
    setSaveSuccess(true);
    
    // Hide success message after 3 seconds
    setTimeout(() => setSaveSuccess(false), 3000);
  };
  
  const handleCancel = () => {
    setIsEditing(false);
    setSaveSuccess(false);
    // Reset form values to current preferences
    setFormValues({
      name: getDisplayName,
      email: email || '',
      avatarUrl: getAvatarUrl,
    });
  };
  
  // Go back to main window
  const handleBack = () => {
    navigate('/');
  };
  
  // Handle logout
  const handleLogout = () => {
    logout();
  };
  
  // More neutral avatar color compatible with system theme
  const avatarColor = theme.palette.mode === 'dark' 
    ? theme.palette.grey[800] 
    : theme.palette.grey[300];
  
  const getInitials = (name?: string) => {
    if (!name) return '?';
    return name
      .split(' ')
      .map((part) => part[0])
      .join('')
      .toUpperCase()
      .substring(0, 2);
  };
  
  if (isLoading && !user) { 
    return (
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          height: '100vh',
        }}
      >
        <CircularProgress />
      </Box>
    );
  }

  if (!user) {
     return (
      <Box sx={{ p: 3 }}>
         <Alert severity="error">Could not load user profile.</Alert>
      </Box>
     );
  }
  
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
      <Box sx={{ display: 'flex', alignItems: 'center', mb: 3, justifyContent: 'space-between' }}>
        <Box sx={{ display: 'flex', alignItems: 'center' }}>
        <IconButton onClick={handleBack} sx={{ mr: 2 }}>
          <ArrowBackIcon />
        </IconButton>
        <Typography variant="h5" component="h1">
          Profile
        </Typography>
        </Box>
        
        <Button
          variant="outlined"
          color="error"
          startIcon={<LogoutIcon />}
          onClick={handleLogout}
        >
          Logout
        </Button>
      </Box>
      
      {saveSuccess && (
        <Alert severity="success" sx={{ mb: 2 }}>
          Profile updated successfully!
        </Alert>
      )}
      
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
        <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', mb: 4 }}>
          <Box sx={{ position: 'relative', mb: 2 }}>
            <Avatar
              src={getAvatarUrl}
              sx={{
                width: 100,
                height: 100,
                bgcolor: avatarColor,
                color: theme.palette.mode === 'dark' 
                  ? theme.palette.grey[300] 
                  : theme.palette.grey[700],
                fontSize: '2rem',
                fontWeight: 500,
                border: `2px solid ${theme.palette.divider}`,
                '&:hover': {
                  bgcolor: theme.palette.mode === 'dark' 
                    ? theme.palette.grey[700] 
                    : theme.palette.grey[400],
                }
              }}
            >
              {!getAvatarUrl && getInitials(getDisplayName)}
            </Avatar>
            
            {isEditing && (
              <Tooltip title="Edit avatar URL in the form below">
                <IconButton
                  sx={{
                    position: 'absolute',
                    bottom: -5,
                    right: -5,
                    bgcolor: theme.palette.primary.main,
                    color: 'white',
                    width: 32,
                    height: 32,
                    '&:hover': {
                      bgcolor: theme.palette.primary.dark,
                    }
                  }}
                >
                  <PhotoCameraIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            )}
          </Box>
          
          <Typography variant="h6" gutterBottom>
            {getDisplayName || 'N/A'}
            {isUsingCustomDisplayName && (
              <Typography component="span" variant="caption" sx={{ ml: 1, opacity: 0.7 }}>
                (Custom)
              </Typography>
            )}
          </Typography>
          
          <Typography variant="body2" color="text.secondary">
            {email || 'N/A'}
          </Typography>
        </Box>
        
        <Divider sx={{ mb: 4 }} />
        
        <Grid container spacing={3}>
          <Grid item xs={12}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
              <Typography variant="h6">
                Personal Information
              </Typography>
              
              <IconButton onClick={handleToggleEdit} color={isEditing ? 'primary' : 'default'}>
                <EditIcon />
              </IconButton>
            </Box>
            
            <Box component="form" noValidate sx={{ mt: 1 }}>
              <TextField
                margin="normal"
                fullWidth
                id="name"
                label="Display Name"
                name="name"
                value={formValues.name}
                onChange={handleChange}
                disabled={!isEditing}
                variant="outlined"
                size="small"
                helperText={isEditing ? "Custom display name (leave empty to use Auth0 name)" : undefined}
              />
              
              {isEditing && (
                <TextField
                  margin="normal"
                  fullWidth
                  id="avatarUrl"
                  label="Avatar URL"
                  name="avatarUrl"
                  value={formValues.avatarUrl}
                  onChange={handleChange}
                  variant="outlined"
                  size="small"
                  helperText="Custom avatar image URL (leave empty to use Auth0 avatar)"
                  placeholder="https://example.com/avatar.jpg"
                />
              )}
              
              <TextField
                margin="normal"
                fullWidth
                id="email"
                label="Email"
                name="email"
                value={formValues.email}
                disabled
                variant="outlined"
                size="small"
                helperText="Email cannot be changed (managed by Auth0)"
              />
              
              {isEditing && (
                <Box sx={{ mt: 3, mb: 2, display: 'flex', gap: 2 }}>
                  <Button
                    variant="contained"
                    color="primary"
                    onClick={handleSave}
                  >
                    Save Changes
                  </Button>
                  <Button
                    variant="outlined"
                    onClick={handleCancel}
                  >
                    Cancel
                  </Button>
                </Box>
              )}
            </Box>
          </Grid>
          
          <Grid item xs={12}>
            <Typography variant="h6" gutterBottom>
              Account Information
            </Typography>
            
            <Box sx={{ mt: 2 }}>
              <Typography variant="body2" gutterBottom>
                <strong>Account ID:</strong> {(user as any).sub || (user as any).id || 'N/A'}
              </Typography>
              
              <Typography variant="body2" gutterBottom>
                <strong>Original Name:</strong> {originalName || 'N/A'}
              </Typography>
              
              {isUsingCustomAvatar && (
                <Typography variant="body2" gutterBottom>
                  <strong>Original Avatar:</strong> {originalPicture ? 'Set' : 'None'}
                </Typography>
              )}
              
              <Typography variant="body2" gutterBottom>
                <strong>Account Type:</strong> Free
              </Typography>
            </Box>
          </Grid>

          <Grid item xs={12}>
            <Typography variant="h6" gutterBottom>
              Support Us
            </Typography>
            
            <Box sx={{ mt: 2 }}>
              <Typography variant="body2" sx={{ mb: 2 }}>
                Love using Denker? Help us continue developing and improving the app by supporting us.
              </Typography>
              <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
              <Button
                variant="outlined"
                color="primary"
                component="a"
                href="https://www.paypal.com/pools/c/9fLtxsD47R"
                target="_blank"
                rel="noopener noreferrer"
                onClick={(e) => {
                  e.preventDefault();
                  // @ts-ignore
                  if (window.electron?.shell?.openExternal) {
                    // @ts-ignore
                    window.electron.shell.openExternal('https://www.paypal.com/pools/c/9fLtxsD47R');
                  } else {
                    window.open('https://www.paypal.com/pools/c/9fLtxsD47R', '_blank', 'noopener,noreferrer');
                  }
                }}
                  sx={{ textTransform: 'none' }}
              >
                Support Us
              </Button>
              </Box>
            </Box>
          </Grid>
        </Grid>
      </Paper>
    </Box>
  );
};

export default ProfilePage; 