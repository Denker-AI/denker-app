import React, { useState, useEffect } from 'react';
import { Box, Typography, Button, TextField, CircularProgress, Paper, Divider, Stack, Tab, Tabs } from '@mui/material';
import useConversationStore from '../store/conversationStore';
import MCPTest from '../components/MCPTest';

// Local storage key for tracking initial conversation creation (must match MainWindow.tsx)
const INITIAL_CONVERSATION_CREATED = 'denker_initial_conversation_created';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;

  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`test-tabpanel-${index}`}
      aria-labelledby={`test-tab-${index}`}
      {...other}
    >
      {value === index && (
        <Box sx={{ p: 3 }}>
          {children}
        </Box>
      )}
    </div>
  );
}

const TestPage: React.FC = () => {
  const [testResponse, setTestResponse] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [apiUrl, setApiUrl] = useState('http://127.0.0.1:8001/api/v1/test');
  const [activeTab, setActiveTab] = useState(0);
  const clearAllConversations = useConversationStore(state => state.clearAllConversations);

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setActiveTab(newValue);
  };

  const testBackendConnection = async () => {
    setIsLoading(true);
    setError(null);
    
    try {
      const response = await fetch(apiUrl);
      const data = await response.json();
      setTestResponse(JSON.stringify(data, null, 2));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to connect to backend');
    } finally {
      setIsLoading(false);
    }
  };

  const handleClearConversations = () => {
    clearAllConversations();
    alert('All conversations have been cleared. Refresh the main page to see the changes.');
  };
  
  const handleResetInitialConversationFlag = () => {
    localStorage.removeItem(INITIAL_CONVERSATION_CREATED);
    alert('Initial conversation flag has been reset. The app will create a new conversation on next startup.');
  };
  
  const handleFullReset = () => {
    clearAllConversations();
    localStorage.removeItem(INITIAL_CONVERSATION_CREATED);
    alert('Full reset completed. All conversations cleared and initial conversation flag reset.');
  };

  return (
    <Box sx={{ 
      display: 'flex', 
      flexDirection: 'column', 
      alignItems: 'center',
      p: 3,
      minHeight: '100vh'
    }}>
      <Paper elevation={3} sx={{ p: 4, maxWidth: 900, width: '100%' }}>
        <Typography variant="h4" gutterBottom>
          Denker App Test Page
        </Typography>
        
        <Tabs value={activeTab} onChange={handleTabChange} sx={{ mb: 2 }}>
          <Tab label="Basic Tests" />
          <Tab label="MCP Test" />
        </Tabs>
        
        <TabPanel value={activeTab} index={0}>
          <Typography variant="body1" paragraph>
            This page helps verify that your frontend is working correctly and can connect to the backend.
          </Typography>
          
          <Box sx={{ mb: 3 }}>
            <TextField
              fullWidth
              label="API URL"
              value={apiUrl}
              onChange={(e) => setApiUrl(e.target.value)}
              margin="normal"
              variant="outlined"
            />
            
            <Button 
              variant="contained" 
              color="primary" 
              onClick={testBackendConnection}
              disabled={isLoading}
              sx={{ mt: 2, mr: 2 }}
            >
              {isLoading ? <CircularProgress size={24} /> : 'Test Backend Connection'}
            </Button>
          </Box>
          
          <Divider sx={{ my: 2 }} />
          
          <Typography variant="h6" gutterBottom>
            Development Tools
          </Typography>
          
          <Stack direction="column" spacing={2} sx={{ mt: 2 }}>
            <Button 
              variant="outlined" 
              color="error" 
              onClick={handleClearConversations}
              fullWidth
            >
              Clear All Conversations
            </Button>
            
            <Button 
              variant="outlined" 
              color="warning" 
              onClick={handleResetInitialConversationFlag}
              fullWidth
            >
              Reset Initial Conversation Flag
            </Button>
            
            <Button 
              variant="contained" 
              color="error" 
              onClick={handleFullReset}
              fullWidth
            >
              Full Reset (Clear All + Reset Flag)
            </Button>
          </Stack>
          
          {error && (
            <Paper 
              elevation={0} 
              sx={{ 
                p: 2, 
                bgcolor: 'error.light', 
                color: 'error.contrastText',
                mb: 2,
                mt: 2
              }}
            >
              <Typography variant="body2">Error: {error}</Typography>
            </Paper>
          )}
          
          {testResponse && (
            <Box sx={{ mt: 2 }}>
              <Typography variant="subtitle1" gutterBottom>Response:</Typography>
              <Paper 
                elevation={0} 
                sx={{ 
                  p: 2, 
                  bgcolor: 'grey.100', 
                  maxHeight: 200, 
                  overflow: 'auto',
                  fontFamily: 'monospace'
                }}
              >
                <pre>{testResponse}</pre>
              </Paper>
            </Box>
          )}
        </TabPanel>
        
        <TabPanel value={activeTab} index={1}>
          <MCPTest />
        </TabPanel>
      </Paper>
    </Box>
  );
};

export default TestPage; 