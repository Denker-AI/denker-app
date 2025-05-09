import React, { useState } from 'react';
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
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import EditIcon from '@mui/icons-material/Edit';
import LogoutIcon from '@mui/icons-material/Logout';
import { useNavigate } from 'react-router-dom';

// Hooks
import useUser from '../hooks/useUser';

// Utils
import { stringToColor } from '../utils/helpers';

const ProfilePage: React.FC = () => {
  const theme = useTheme();
  const navigate = useNavigate();
  const { profile, updateUserProfile, isLoading, logout } = useUser();
  
  // Local state for form values
  const [formValues, setFormValues] = useState({
    name: profile?.name || '',
    email: profile?.email || '',
  });
  
  const [isEditing, setIsEditing] = useState(false);
  
  // Handle form changes
  const handleChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setFormValues({
      ...formValues,
      [event.target.name]: event.target.value,
    });
  };
  
  // Toggle edit mode
  const handleToggleEdit = () => {
    setIsEditing(!isEditing);
    
    // Reset form values when canceling edit
    if (isEditing) {
      setFormValues({
        name: profile?.name || '',
        email: profile?.email || '',
      });
    }
  };
  
  // Save profile
  const handleSave = async () => {
    await updateUserProfile({
      name: formValues.name,
    });
    setIsEditing(false);
  };
  
  // Go back to main window
  const handleBack = () => {
    navigate('/');
  };
  
  // Handle logout
  const handleLogout = () => {
    logout();
  };
  
  // Use a neutral color for avatar instead of generating one based on name
  const avatarColor = theme.palette.grey[700]; // Neutral dark grey color
  
  // Get initials for avatar
  const getInitials = (name: string) => {
    return name
      .split(' ')
      .map((part) => part[0])
      .join('')
      .toUpperCase()
      .substring(0, 2);
  };
  
  if (!profile) {
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
          <Avatar
            src={profile.picture}
            sx={{
              width: 100,
              height: 100,
              mb: 2,
              bgcolor: avatarColor,
              fontSize: '2rem',
            }}
          >
            {!profile.picture && getInitials(profile.name)}
          </Avatar>
          
          <Typography variant="h6" gutterBottom>
            {profile.name}
          </Typography>
          
          <Typography variant="body2" color="text.secondary">
            {profile.email}
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
                label="Name"
                name="name"
                value={formValues.name}
                onChange={handleChange}
                disabled={!isEditing}
                variant="outlined"
                size="small"
              />
              
              <TextField
                margin="normal"
                fullWidth
                id="email"
                label="Email"
                name="email"
                value={formValues.email}
                disabled={true} // Email is managed by Auth0
                variant="outlined"
                size="small"
                helperText="Email is managed by your authentication provider"
              />
              
              {isEditing && (
                <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 2 }}>
                  <Button
                    variant="outlined"
                    onClick={handleToggleEdit}
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
              )}
            </Box>
          </Grid>
          
          <Grid item xs={12}>
            <Typography variant="h6" gutterBottom>
              Account Information
            </Typography>
            
            <Box sx={{ mt: 2 }}>
              <Typography variant="body2" gutterBottom>
                <strong>Account ID:</strong> {profile.id}
              </Typography>
              
              <Typography variant="body2" gutterBottom>
                <strong>Account Type:</strong> Free
              </Typography>
            </Box>
          </Grid>
        </Grid>
      </Paper>
    </Box>
  );
};

export default ProfilePage; 