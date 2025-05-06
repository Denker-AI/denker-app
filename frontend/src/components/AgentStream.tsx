import React, { useEffect } from 'react';
import { Box, Typography, CircularProgress, Card, CardContent, Divider, Chip } from '@mui/material';
import useAgentWebSocket, { AgentStepType } from '../services/agentWebSocket';

interface AgentStreamProps {
  queryId: string;
  onComplete?: (steps: any[]) => void;
}

const AgentStream: React.FC<AgentStreamProps> = ({ queryId, onComplete }) => {
  const { 
    streamingSteps, 
    status, 
    error, 
    isConnected 
  } = useAgentWebSocket(queryId);

  useEffect(() => {
    if (status === 'Finished' && onComplete) {
      onComplete(streamingSteps);
    }
  }, [status, streamingSteps, onComplete]);

  if (error) {
    return (
      <Box sx={{ p: 2, color: 'error.main' }}>
        <Typography variant="body1">Error: {error}</Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ p: 2 }}>
      {status !== 'idle' && status !== 'Finished' && isConnected && (
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
          <CircularProgress size={20} sx={{ mr: 1 }} />
          <Typography variant="body2" color="text.secondary">
            Processing your request...
          </Typography>
        </Box>
      )}

      {streamingSteps.map((step, index) => (
        <Box key={index} sx={{ mb: 2 }}>
          {renderStep(step, index)}
        </Box>
      ))}

      {status === 'Finished' && (
        <Box sx={{ mt: 2 }}>
          <Chip 
            label="Completed" 
            color="success" 
            size="small" 
            sx={{ mr: 1 }} 
          />
        </Box>
      )}
    </Box>
  );
};

const renderStep = (step: any, index: number) => {
  switch (step.type) {
    case 'Starting':
    case 'Loaded':
    case 'Running':
    case 'Initialized':
    case 'Chatting':
    case 'Routing':
    case 'Planning':
    case 'Ready':
      return (
        <Card variant="outlined" sx={{ mb: 2, bgcolor: 'background.paper' }}>
          <CardContent>
            <Typography variant="caption" color="text.secondary">
              {step.type}
            </Typography>
            <Typography variant="body1" sx={{ whiteSpace: 'pre-wrap' }}>
              {step.content}
            </Typography>
          </CardContent>
        </Card>
      );
      
    case 'Calling Tool':
      return (
        <Card variant="outlined" sx={{ mb: 2, bgcolor: 'action.hover' }}>
          <CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
              <Chip 
                label={`${step.type}: ${step.tool || 'Unknown tool'}`} 
                size="small" 
                color="primary" 
                sx={{ mr: 1 }} 
              />
              {step.query && (
                <Typography variant="body2" color="text.secondary">
                  Query: {step.query}
                </Typography>
              )}
            </Box>
          </CardContent>
        </Card>
      );
      
    case 'Finished':
      return (
        <Card variant="outlined" sx={{ mb: 2, bgcolor: 'success.light', color: 'white' }}>
          <CardContent>
            <Typography variant="h6" sx={{ mb: 1 }}>
              Final Answer
            </Typography>
            <Typography variant="body1" sx={{ whiteSpace: 'pre-wrap' }}>
              {typeof step.content === 'string' ? step.content : JSON.stringify(step.content, null, 2)}
            </Typography>
            
            {step.content && step.content.citations && (
              <>
                <Divider sx={{ my: 2 }} />
                <Typography variant="subtitle2">
                  Citations:
                </Typography>
                <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
                  {step.content.citations}
                </Typography>
              </>
            )}
          </CardContent>
        </Card>
      );
      
    case 'Error':
      return (
        <Card variant="outlined" sx={{ mb: 2, bgcolor: 'error.light', color: 'white' }}>
          <CardContent>
            <Typography variant="h6" sx={{ mb: 1 }}>
              Error
            </Typography>
            <Typography variant="body1" sx={{ whiteSpace: 'pre-wrap' }}>
              {step.content}
            </Typography>
          </CardContent>
        </Card>
      );
      
    case 'Shutdown':
      return (
        <Card variant="outlined" sx={{ mb: 2, bgcolor: 'warning.light' }}>
          <CardContent>
            <Typography variant="caption" color="text.secondary">
              Process Ended
            </Typography>
            <Typography variant="body1" sx={{ whiteSpace: 'pre-wrap' }}>
              {step.content}
            </Typography>
          </CardContent>
        </Card>
      );
      
    default:
      return (
        <Typography variant="body2" color="text.secondary">
          {step.type}: {typeof step.content === 'string' ? step.content : JSON.stringify(step.content)}
        </Typography>
      );
  }
};

const renderDocResults = (content: any) => {
  if (!content || !content.results || content.results.length === 0) {
    return <Typography>No document results found.</Typography>;
  }
  
  return (
    <Box>
      <Typography variant="body2" sx={{ mb: 1 }}>
        Found {content.total} document matches
      </Typography>
      
      {content.results.slice(0, 3).map((result: any, idx: number) => (
        <Box key={idx} sx={{ mb: 1, p: 1, bgcolor: 'background.paper', borderRadius: 1 }}>
          <Typography variant="subtitle2">
            {result.title || 'Untitled Document'}
          </Typography>
          <Typography variant="body2">
            {result.content.length > 200 
              ? `${result.content.substring(0, 200)}...` 
              : result.content}
          </Typography>
        </Box>
      ))}
    </Box>
  );
};

const renderWebResults = (content: any) => {
  if (!content || !content.results || content.results.length === 0) {
    return <Typography>No web results found.</Typography>;
  }
  
  return (
    <Box>
      <Typography variant="body2" sx={{ mb: 1 }}>
        Found {content.total} web matches
      </Typography>
      
      {content.results.slice(0, 3).map((result: any, idx: number) => (
        <Box key={idx} sx={{ mb: 1, p: 1, bgcolor: 'background.paper', borderRadius: 1 }}>
          <Typography variant="subtitle2">
            {result.title || 'Untitled'}
          </Typography>
          <Typography variant="caption" component="div" color="primary">
            {result.url}
          </Typography>
          <Typography variant="body2">
            {result.snippet}
          </Typography>
        </Box>
      ))}
    </Box>
  );
};

const renderFileResults = (content: any) => {
  if (!content || !content.files || content.files.length === 0) {
    return <Typography>No file results found.</Typography>;
  }
  
  return (
    <Box>
      <Typography variant="body2" sx={{ mb: 1 }}>
        Found {content.total} file matches
      </Typography>
      
      {content.files.slice(0, 3).map((file: any, idx: number) => (
        <Box key={idx} sx={{ mb: 1, p: 1, bgcolor: 'background.paper', borderRadius: 1 }}>
          <Typography variant="subtitle2">
            {file.path}
          </Typography>
          <Typography variant="caption" component="div">
            {file.size} bytes
          </Typography>
        </Box>
      ))}
    </Box>
  );
};

export default AgentStream; 