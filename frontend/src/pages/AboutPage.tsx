import React from 'react';
import {
  Box,
  Typography,
  Paper,
  IconButton,
  Divider,
  List,
  ListItem,
  ListItemText,
  Link,
  useTheme,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { useNavigate } from 'react-router-dom';

const AboutPage: React.FC = () => {
  const theme = useTheme();
  const navigate = useNavigate();
  
  // App version
  const appVersion = '1.0.0';
  
  // Handle back navigation
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
          About Denker
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
        <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', mb: 4 }}>
          <Box
            component="img"
            src="/logo.png"
            alt="Denker Logo"
            sx={{
              width: 120,
              height: 120,
              mb: 2,
            }}
          />
          
          <Typography variant="h4" gutterBottom>
            Denker
          </Typography>
          
          <Typography variant="subtitle1" color="text.secondary" gutterBottom>
            Your AI-powered desktop assistant
          </Typography>
          
          <Typography variant="body2" color="text.secondary">
            Version {appVersion}
          </Typography>
        </Box>
        
        <Divider sx={{ mb: 4 }} />
        
        <Typography variant="h6" gutterBottom>
          About
        </Typography>
        
        <Typography variant="body1" paragraph>
          Denker is an AI-powered desktop assistant designed to help you with various tasks, 
          from answering questions to analyzing documents and providing insights. 
          Built with cutting-edge AI technology, Denker aims to enhance your productivity 
          and make complex tasks simpler.
        </Typography>
        
        <Typography variant="body1" paragraph>
          Our mission is to create an intelligent assistant that understands your needs, 
          learns from your interactions, and provides valuable assistance across different domains.
        </Typography>
        
        <Divider sx={{ my: 4 }} />
        
        <Typography variant="h6" gutterBottom>
          Features
        </Typography>
        
        <List>
          <ListItem>
            <ListItemText 
              primary="Natural Language Processing" 
              secondary="Communicate with Denker using natural language for a seamless experience"
            />
          </ListItem>
          <ListItem>
            <ListItemText 
              primary="Document Analysis" 
              secondary="Upload and analyze documents to extract insights and information"
            />
          </ListItem>
          <ListItem>
            <ListItemText 
              primary="Web Search" 
              secondary="Search the web and get summarized results without leaving the app"
            />
          </ListItem>
          <ListItem>
            <ListItemText 
              primary="Conversation History" 
              secondary="Keep track of your conversations and refer back to them anytime"
            />
          </ListItem>
          <ListItem>
            <ListItemText 
              primary="Cross-Platform" 
              secondary="Available on macOS and Windows for a consistent experience across devices"
            />
          </ListItem>
        </List>
        
        <Divider sx={{ my: 4 }} />
        
        <Typography variant="h6" gutterBottom>
          Technologies
        </Typography>
        
        <Typography variant="body1" paragraph>
          Denker is built using modern technologies including:
        </Typography>
        
        <List dense>
          <ListItem>
            <ListItemText primary="React & TypeScript" secondary="For a responsive and type-safe frontend" />
          </ListItem>
          <ListItem>
            <ListItemText primary="Electron" secondary="For cross-platform desktop application support" />
          </ListItem>
          <ListItem>
            <ListItemText primary="FastAPI" secondary="For a high-performance backend API" />
          </ListItem>
          <ListItem>
            <ListItemText primary="Google Vertex AI" secondary="For advanced AI capabilities" />
          </ListItem>
          <ListItem>
            <ListItemText primary="Milvus" secondary="For vector database and semantic search" />
          </ListItem>
        </List>
        
        <Divider sx={{ my: 4 }} />
        
        <Typography variant="h6" gutterBottom>
          Legal
        </Typography>
        
        <Typography variant="body2" paragraph>
          © 2023 Denker AI. All rights reserved.
        </Typography>
        
        <Box sx={{ display: 'flex', gap: 2 }}>
          <Link href="#" underline="hover" color="inherit">
            Terms of Service
          </Link>
          <Link 
            component="button" 
            underline="hover" 
            color="inherit" 
            onClick={() => navigate('/privacy')}
          >
            Privacy Policy
          </Link>
          <Link href="#" underline="hover" color="inherit">
            License
          </Link>
        </Box>
      </Paper>
    </Box>
  );
};

export default AboutPage; 