import React, { useState } from 'react';
import { Box, Typography, TextField, Button, Paper, CircularProgress } from '@mui/material';
import MCPAgentClient from '../utils/mcp-agent-client';

const MCPTest: React.FC = () => {
  const [query, setQuery] = useState('');
  const [response, setResponse] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const mcpAgentClient = new MCPAgentClient();
  
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    
    setLoading(true);
    setError(null);
    setResponse(null);
    
    try {
      const result = await mcpAgentClient.processRequest(query, {
        realtime: true,
        conversation_id: 'test-conversation'
      });
      
      setResponse(JSON.stringify(result, null, 2));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred while processing your request');
    } finally {
      setLoading(false);
    }
  };
  
  return (
    <Box>
      <Typography variant="h6" gutterBottom>
        MCP Agent Test
      </Typography>
      
      <Paper elevation={0} sx={{ p: 2, bgcolor: 'grey.100', mb: 3 }}>
        <Typography variant="body2">
          This component tests the direct connection to the MCP Agent. Enter a query below to test the agent's response.
        </Typography>
      </Paper>
      
      <form onSubmit={handleSubmit}>
        <TextField
          fullWidth
          label="Enter query for MCP Agent"
          variant="outlined"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          disabled={loading}
          margin="normal"
        />
        
        <Button 
          type="submit" 
          variant="contained" 
          color="primary" 
          disabled={loading || !query.trim()}
          sx={{ mt: 2 }}
        >
          {loading ? <CircularProgress size={24} /> : 'Send Query'}
        </Button>
      </form>
      
      {error && (
        <Paper 
          elevation={0} 
          sx={{ 
            p: 2, 
            bgcolor: 'error.light', 
            color: 'error.contrastText',
            mt: 3
          }}
        >
          <Typography variant="body2">Error: {error}</Typography>
        </Paper>
      )}
      
      {response && (
        <Box sx={{ mt: 3 }}>
          <Typography variant="subtitle1" gutterBottom>Response:</Typography>
          <Paper 
            elevation={0} 
            sx={{ 
              p: 2, 
              bgcolor: 'grey.100', 
              maxHeight: 400, 
              overflow: 'auto',
              fontFamily: 'monospace'
            }}
          >
            <pre>{response}</pre>
          </Paper>
        </Box>
      )}
    </Box>
  );
};

export default MCPTest; 