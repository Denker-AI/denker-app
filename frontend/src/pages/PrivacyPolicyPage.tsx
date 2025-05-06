import React from 'react';
import {
  Box,
  Typography,
  Paper,
  IconButton,
  Divider,
  useTheme,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { useNavigate } from 'react-router-dom';

const PrivacyPolicyPage: React.FC = () => {
  const theme = useTheme();
  const navigate = useNavigate();
  
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
          Privacy Policy
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
        <Typography variant="h6" gutterBottom>
          Last Updated: June 1, 2023
        </Typography>
        
        <Typography variant="body1" paragraph>
          At Denker, we take your privacy seriously. This Privacy Policy explains how we collect, use, 
          disclose, and safeguard your information when you use our desktop application.
        </Typography>
        
        <Divider sx={{ my: 3 }} />
        
        <Typography variant="h6" gutterBottom>
          Information We Collect
        </Typography>
        
        <Typography variant="subtitle1" gutterBottom>
          Personal Information
        </Typography>
        
        <Typography variant="body1" paragraph>
          We may collect personal information that you voluntarily provide when using Denker, including:
        </Typography>
        
        <ul>
          <li>
            <Typography variant="body1" paragraph>
              Name, email address, and other contact information when you create an account
            </Typography>
          </li>
          <li>
            <Typography variant="body1" paragraph>
              Profile information and preferences
            </Typography>
          </li>
          <li>
            <Typography variant="body1" paragraph>
              Content of conversations with the AI assistant
            </Typography>
          </li>
          <li>
            <Typography variant="body1" paragraph>
              Files and documents you upload for analysis
            </Typography>
          </li>
          <li>
            <Typography variant="body1" paragraph>
              Feedback and support requests
            </Typography>
          </li>
        </ul>
        
        <Typography variant="subtitle1" gutterBottom>
          Usage Information
        </Typography>
        
        <Typography variant="body1" paragraph>
          We automatically collect certain information about your device and how you interact with Denker, including:
        </Typography>
        
        <ul>
          <li>
            <Typography variant="body1" paragraph>
              Device information (operating system, hardware model, etc.)
            </Typography>
          </li>
          <li>
            <Typography variant="body1" paragraph>
              Log data (IP address, access times, features used)
            </Typography>
          </li>
          <li>
            <Typography variant="body1" paragraph>
              Usage patterns and preferences
            </Typography>
          </li>
          <li>
            <Typography variant="body1" paragraph>
              Performance data and error reports
            </Typography>
          </li>
        </ul>
        
        <Divider sx={{ my: 3 }} />
        
        <Typography variant="h6" gutterBottom>
          How We Use Your Information
        </Typography>
        
        <Typography variant="body1" paragraph>
          We use the information we collect for various purposes, including:
        </Typography>
        
        <ul>
          <li>
            <Typography variant="body1" paragraph>
              Providing, maintaining, and improving Denker's functionality
            </Typography>
          </li>
          <li>
            <Typography variant="body1" paragraph>
              Personalizing your experience and preferences
            </Typography>
          </li>
          <li>
            <Typography variant="body1" paragraph>
              Processing and storing your conversations and uploaded files
            </Typography>
          </li>
          <li>
            <Typography variant="body1" paragraph>
              Training and improving our AI models (in anonymized form)
            </Typography>
          </li>
          <li>
            <Typography variant="body1" paragraph>
              Communicating with you about updates, features, and support
            </Typography>
          </li>
          <li>
            <Typography variant="body1" paragraph>
              Analyzing usage patterns to improve our service
            </Typography>
          </li>
          <li>
            <Typography variant="body1" paragraph>
              Detecting and preventing fraudulent or unauthorized activity
            </Typography>
          </li>
        </ul>
        
        <Divider sx={{ my: 3 }} />
        
        <Typography variant="h6" gutterBottom>
          Data Sharing and Disclosure
        </Typography>
        
        <Typography variant="body1" paragraph>
          We do not sell your personal information. We may share your information in the following circumstances:
        </Typography>
        
        <ul>
          <li>
            <Typography variant="body1" paragraph>
              <strong>Service Providers:</strong> We may share information with third-party vendors who provide services on our behalf, such as hosting, analytics, and customer support.
            </Typography>
          </li>
          <li>
            <Typography variant="body1" paragraph>
              <strong>Compliance and Safety:</strong> We may disclose information if required by law or if we believe it's necessary to protect our rights, safety, or the rights and safety of others.
            </Typography>
          </li>
          <li>
            <Typography variant="body1" paragraph>
              <strong>Business Transfers:</strong> If Denker is involved in a merger, acquisition, or sale of assets, your information may be transferred as part of that transaction.
            </Typography>
          </li>
          <li>
            <Typography variant="body1" paragraph>
              <strong>With Your Consent:</strong> We may share information with your consent or at your direction.
            </Typography>
          </li>
        </ul>
        
        <Divider sx={{ my: 3 }} />
        
        <Typography variant="h6" gutterBottom>
          Data Security
        </Typography>
        
        <Typography variant="body1" paragraph>
          We implement appropriate technical and organizational measures to protect your information from unauthorized access, loss, or alteration. These measures include encryption, access controls, and regular security assessments.
        </Typography>
        
        <Typography variant="body1" paragraph>
          However, no method of transmission or storage is 100% secure. While we strive to protect your information, we cannot guarantee absolute security.
        </Typography>
        
        <Divider sx={{ my: 3 }} />
        
        <Typography variant="h6" gutterBottom>
          Your Rights and Choices
        </Typography>
        
        <Typography variant="body1" paragraph>
          Depending on your location, you may have certain rights regarding your personal information, including:
        </Typography>
        
        <ul>
          <li>
            <Typography variant="body1" paragraph>
              Accessing, correcting, or deleting your information
            </Typography>
          </li>
          <li>
            <Typography variant="body1" paragraph>
              Restricting or objecting to our processing of your information
            </Typography>
          </li>
          <li>
            <Typography variant="body1" paragraph>
              Requesting a copy of your information in a portable format
            </Typography>
          </li>
          <li>
            <Typography variant="body1" paragraph>
              Withdrawing consent where processing is based on consent
            </Typography>
          </li>
        </ul>
        
        <Typography variant="body1" paragraph>
          You can exercise these rights by contacting us at privacy@denker.ai.
        </Typography>
        
        <Divider sx={{ my: 3 }} />
        
        <Typography variant="h6" gutterBottom>
          Changes to This Policy
        </Typography>
        
        <Typography variant="body1" paragraph>
          We may update this Privacy Policy from time to time. We will notify you of any changes by posting the new policy on this page and updating the "Last Updated" date.
        </Typography>
        
        <Typography variant="body1" paragraph>
          We encourage you to review this Privacy Policy periodically to stay informed about how we are protecting your information.
        </Typography>
        
        <Divider sx={{ my: 3 }} />
        
        <Typography variant="h6" gutterBottom>
          Contact Us
        </Typography>
        
        <Typography variant="body1" paragraph>
          If you have any questions or concerns about this Privacy Policy or our data practices, please contact us at:
        </Typography>
        
        <Typography variant="body1" paragraph>
          Email: privacy@denker.ai
        </Typography>
        
        <Typography variant="body1" paragraph>
          Address: 123 AI Street, San Francisco, CA 94103
        </Typography>
      </Paper>
    </Box>
  );
};

export default PrivacyPolicyPage; 