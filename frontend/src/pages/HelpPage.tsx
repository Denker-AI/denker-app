import React, { useState } from 'react';
import {
  Box,
  Typography,
  Paper,
  IconButton,
  Divider,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  useTheme,
  Tabs,
  Tab,
  Button,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import HelpOutlineIcon from '@mui/icons-material/HelpOutline';
import ChatIcon from '@mui/icons-material/Chat';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import SearchIcon from '@mui/icons-material/Search';
import SettingsIcon from '@mui/icons-material/Settings';
import ContactSupportIcon from '@mui/icons-material/ContactSupport';
import { useNavigate } from 'react-router-dom';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

const TabPanel = (props: TabPanelProps) => {
  const { children, value, index, ...other } = props;

  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`help-tabpanel-${index}`}
      aria-labelledby={`help-tab-${index}`}
      {...other}
      style={{ height: '100%', overflow: 'auto' }}
    >
      {value === index && (
        <Box sx={{ p: 2 }}>
          {children}
        </Box>
      )}
    </div>
  );
};

const HelpPage: React.FC = () => {
  const theme = useTheme();
  const navigate = useNavigate();
  const [tabValue, setTabValue] = useState(0);
  
  // Handle back navigation
  const handleBack = () => {
    navigate('/');
  };
  
  // Handle tab change
  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setTabValue(newValue);
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
          Help & Support
        </Typography>
      </Box>
      
      <Paper
        elevation={0}
        sx={{
          display: 'flex',
          flexDirection: 'column',
          backgroundColor: 'rgba(30, 30, 30, 0.6)',
          backdropFilter: 'blur(10px)',
          border: '1px solid rgba(255, 255, 255, 0.1)',
          borderRadius: 2,
          flexGrow: 1,
          overflow: 'hidden',
        }}
      >
        <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
          <Tabs 
            value={tabValue} 
            onChange={handleTabChange} 
            variant="fullWidth"
            textColor="primary"
            indicatorColor="primary"
          >
            <Tab label="Getting Started" icon={<HelpOutlineIcon />} iconPosition="start" />
            <Tab label="Features" icon={<ChatIcon />} iconPosition="start" />
            <Tab label="FAQ" icon={<SearchIcon />} iconPosition="start" />
          </Tabs>
        </Box>
        
        {/* Getting Started Tab */}
        <TabPanel value={tabValue} index={0}>
          <Typography variant="h6" gutterBottom>
            Welcome to Denker
          </Typography>
          
          <Typography variant="body1" paragraph>
            Denker is your AI-powered desktop assistant designed to help you with various tasks.
            This guide will help you get started with the basic features.
          </Typography>
          
          <Divider sx={{ my: 2 }} />
          
          <Typography variant="subtitle1" gutterBottom>
            Basic Navigation
          </Typography>
          
          <List>
            <ListItem>
              <ListItemIcon>
                <ChatIcon />
              </ListItemIcon>
              <ListItemText 
                primary="Main Window" 
                secondary="This is where you can chat with Denker. Ask questions, request information, or give commands."
              />
            </ListItem>
            <ListItem>
              <ListItemIcon>
                <UploadFileIcon />
              </ListItemIcon>
              <ListItemText 
                primary="File Upload" 
                secondary="Upload documents for analysis by clicking the attachment button in the chat input."
              />
            </ListItem>
            <ListItem>
              <ListItemIcon>
                <SettingsIcon />
              </ListItemIcon>
              <ListItemText 
                primary="Settings" 
                secondary="Customize your experience through the settings page, accessible from the side menu."
              />
            </ListItem>
          </List>
          
          <Divider sx={{ my: 2 }} />
          
          <Typography variant="subtitle1" gutterBottom>
            First Steps
          </Typography>
          
          <Typography variant="body1" paragraph>
            1. Start a new conversation by typing a message in the input box.
          </Typography>
          <Typography variant="body1" paragraph>
            2. Try asking Denker a question or requesting information.
          </Typography>
          <Typography variant="body1" paragraph>
            3. Upload a document to analyze its contents.
          </Typography>
          <Typography variant="body1" paragraph>
            4. Explore the side menu to access your conversation history, files, and settings.
          </Typography>
        </TabPanel>
        
        {/* Features Tab */}
        <TabPanel value={tabValue} index={1}>
          <Typography variant="h6" gutterBottom>
            Key Features
          </Typography>
          
          <Accordion>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography variant="subtitle1">Natural Language Processing</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <Typography variant="body1" paragraph>
                Denker understands natural language, allowing you to communicate as you would with a human assistant.
                You can ask questions, request information, or give commands in plain English.
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Example: "Summarize the key points from the document I uploaded" or "What's the weather like in New York today?"
              </Typography>
            </AccordionDetails>
          </Accordion>
          
          <Accordion>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography variant="subtitle1">Document Analysis</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <Typography variant="body1" paragraph>
                Upload documents for Denker to analyze. Denker can extract information, summarize content,
                answer questions about the document, and more.
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Supported formats: PDF, DOCX, TXT, CSV, and more.
              </Typography>
            </AccordionDetails>
          </Accordion>
          
          <Accordion>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography variant="subtitle1">Web Search</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <Typography variant="body1" paragraph>
                Denker can search the web to provide you with up-to-date information on various topics.
                Simply ask a question, and Denker will retrieve relevant information from the internet.
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Example: "What are the latest developments in renewable energy?" or "Find news about SpaceX launches"
              </Typography>
            </AccordionDetails>
          </Accordion>
          
          <Accordion>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography variant="subtitle1">Conversation History</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <Typography variant="body1" paragraph>
                Denker keeps track of your conversations, allowing you to refer back to previous interactions.
                Access your conversation history through the side menu.
              </Typography>
              <Typography variant="body2" color="text.secondary">
                You can also start a new conversation at any time by clicking the "New Conversation" button.
              </Typography>
            </AccordionDetails>
          </Accordion>
          
          <Accordion>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography variant="subtitle1">File Management</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <Typography variant="body1" paragraph>
                Upload, view, and manage your files through the Files page. Denker keeps track of the files
                you've uploaded and allows you to access them at any time.
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Access your files through the "Files" tab in the side menu.
              </Typography>
            </AccordionDetails>
          </Accordion>
        </TabPanel>
        
        {/* FAQ Tab */}
        <TabPanel value={tabValue} index={2}>
          <Typography variant="h6" gutterBottom>
            Frequently Asked Questions
          </Typography>
          
          <Accordion>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography variant="subtitle1">What can I ask Denker?</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <Typography variant="body1">
                You can ask Denker a wide range of questions, from general knowledge queries to specific
                requests for information. Denker can also analyze documents, search the web, and perform
                various tasks based on your instructions.
              </Typography>
            </AccordionDetails>
          </Accordion>
          
          <Accordion>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography variant="subtitle1">Is my data secure?</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <Box>
                <Typography variant="body1" paragraph>
                  Yes, Denker takes data security seriously. Your conversations and uploaded files are
                  encrypted and stored securely. We do not share your data with third parties without
                  your consent. For more information, please refer to our Privacy Policy.
                </Typography>
                <Button
                  variant="outlined"
                  size="small"
                  onClick={() => navigate('/privacy')}
                >
                  View Privacy Policy
                </Button>
              </Box>
            </AccordionDetails>
          </Accordion>
          
          <Accordion>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography variant="subtitle1">What file types are supported?</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <Typography variant="body1">
                Denker supports various file types, including PDF, DOCX, TXT, CSV, images (JPG, PNG),
                and more. The maximum file size is 10MB per file, and you can upload up to 5 files at once.
              </Typography>
            </AccordionDetails>
          </Accordion>
          
          <Accordion>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography variant="subtitle1">How do I start a new conversation?</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <Typography variant="body1">
                You can start a new conversation by clicking the "New Conversation" button in the top
                navigation bar. This will create a fresh conversation thread where you can begin
                interacting with Denker.
              </Typography>
            </AccordionDetails>
          </Accordion>
          
          <Accordion>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography variant="subtitle1">Can I use Denker offline?</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <Typography variant="body1">
                Denker requires an internet connection to function properly, as it relies on cloud-based
                AI services. However, you can view your conversation history and previously uploaded
                files while offline.
              </Typography>
            </AccordionDetails>
          </Accordion>
          
          <Accordion>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography variant="subtitle1">How do I provide feedback?</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <Typography variant="body1">
                We value your feedback! You can provide feedback by clicking on the "Feedback" option
                in the side menu. This will open a form where you can submit bug reports, feature
                requests, or general feedback about your experience with Denker.
              </Typography>
            </AccordionDetails>
          </Accordion>
          
          <Accordion>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography variant="subtitle1">How do I contact support?</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <Box>
                <Typography variant="body1" paragraph>
                  If you need assistance or have specific questions, you can contact our support team through the Contact page.
                </Typography>
                <Button
                  variant="outlined"
                  startIcon={<ContactSupportIcon />}
                  onClick={() => navigate('/contact')}
                >
                  Contact Support
                </Button>
              </Box>
            </AccordionDetails>
          </Accordion>
        </TabPanel>
      </Paper>
    </Box>
  );
};

export default HelpPage;

 