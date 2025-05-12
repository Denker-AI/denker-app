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
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import EditIcon from '@mui/icons-material/Edit';
import LogoutIcon from '@mui/icons-material/Logout';
import { useNavigate } from 'react-router-dom';

// REMOVE custom hook
// import useUser from '../hooks/useUser'; 
import { useAuth } from '../auth/AuthContext'; // CORRECTED PATH: Changed ../../ to ../

// Utils
import { stringToColor } from '../utils/helpers';

const ProfilePage: React.FC = () => {
  const theme = useTheme();
  const navigate = useNavigate();
  // const { profile, updateUserProfile, isLoading, logout } = useUser(); // REMOVED
  const { user, logout, isLoading } = useAuth(); // ADDED: Get user and logout from context
  
  // Local state for form values (keep for potential future editing)
  const [formValues, setFormValues] = useState({
    name: user?.name || '',
    email: user?.email || '',
  });
  
  // Keep track of initial load from context
  useEffect(() => {
    if (user) {
      setFormValues({
        name: user.name || '',
        email: user.email || '',
      });
    }
  }, [user]); // Update form if user object changes

  // Editing is disabled for now as update logic is removed
  const [isEditing, setIsEditing] = useState(false);
  
  const handleChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setFormValues({
      ...formValues,
      [event.target.name]: event.target.value,
    });
  };
  
  // Disable editing toggle for now
  const handleToggleEdit = () => {
    // setIsEditing(!isEditing);
    console.log('Profile editing is currently disabled.'); 
  };
  
  // Disable save functionality for now
  const handleSave = async () => {
    // await updateUserProfile({ name: formValues.name });
    // setIsEditing(false);
    console.log('Profile saving is currently disabled.');
  };
  
  // Go back to main window
  const handleBack = () => {
    navigate('/');
  };
  
  // Handle logout (uses logout from useAuth)
  const handleLogout = () => {
    logout();
  };
  
  const avatarColor = theme.palette.grey[700];
  
  const getInitials = (name?: string) => {
    if (!name) return '?';
    return name
      .split(' ')
      .map((part) => part[0])
      .join('')
      .toUpperCase()
      .substring(0, 2);
  };
  
  // Use isLoading from useAuth for initial loading state
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

  // Handle case where user is still null after loading (shouldn't happen if route is protected)
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
            src={user.picture} // Use user.picture from context
            sx={{
              width: 100,
              height: 100,
              mb: 2,
              bgcolor: avatarColor,
              fontSize: '2rem',
            }}
          >
            {/* Use user.name for initials, handle undefined case */}
            {!user.picture && getInitials(user.name)}
          </Avatar>
          
          <Typography variant="h6" gutterBottom>
            {user.name || 'N/A'} {/* Use user.name */} 
          </Typography>
          
          <Typography variant="body2" color="text.secondary">
            {user.email || 'N/A'} {/* Use user.email */}
          </Typography>
        </Box>
        
        <Divider sx={{ mb: 4 }} />
        
        <Grid container spacing={3}>
          <Grid item xs={12}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
              <Typography variant="h6">
                Personal Information
              </Typography>
              
              {/* Disable Edit button for now */}
              <IconButton onClick={handleToggleEdit} color={isEditing ? 'primary' : 'default'} disabled>
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
                value={formValues.name} // Use local state derived from user.name
                onChange={handleChange}
                disabled={!isEditing} // Still controlled by isEditing state
                variant="outlined"
                size="small"
              />
              
              <TextField
                margin="normal"
                fullWidth
                id="email"
                label="Email"
                name="email"
                value={formValues.email} // Use local state derived from user.email
                disabled // Email usually not editable
                variant="outlined"
                size="small"
              />
              
              {isEditing && (
                <Button
                  type="button" // Changed from submit to button as we use handleSave
                  variant="contained"
                  color="primary"
                  sx={{ mt: 3, mb: 2 }}
                  onClick={handleSave}
                  disabled // Disable save button for now
                >
                  Save Changes
                </Button>
              )}
            </Box>
          </Grid>
          
          <Grid item xs={12}>
            <Typography variant="h6" gutterBottom>
              Account Information
            </Typography>
            
            <Box sx={{ mt: 2 }}>
              <Typography variant="body2" gutterBottom>
                <strong>Account ID:</strong> {user.id}
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