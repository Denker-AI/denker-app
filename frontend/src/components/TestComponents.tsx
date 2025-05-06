import React, { useState } from 'react';
import { 
  Box, 
  Typography, 
  Paper, 
  Button, 
  Container,
  Grid,
  Divider,
  useTheme,
  Tabs,
  Tab
} from '@mui/material';
import { alpha } from '@mui/material/styles';
import ClarificationPrompt from './ClarificationPrompt';

// Sample data
const sampleMessages = [
  {
    id: 'user_1',
    content: 'Hello, can you help me with my research about climate change?',
    role: 'user',
    timestamp: new Date()
  },
  {
    id: 'assistant_1',
    content: 'I\'d be happy to help with your climate change research. What specific aspects are you interested in?',
    role: 'assistant',
    timestamp: new Date()
  },
  {
    id: 'user_2',
    content: 'I need information about recent trends and solutions.',
    role: 'user',
    timestamp: new Date()
  }
];

const sampleStreamingSteps = [
  {
    type: 'thinking',
    content: 'I need to gather information about recent climate change trends and solutions.'
  },
  {
    type: 'tool_call',
    content: 'Searching for recent climate data',
    tool: 'web-search',
    query: 'recent climate change trends 2023 data'
  },
  {
    type: 'result',
    content: 'Found 3 relevant articles about climate trends in 2023',
    source: 'web'
  },
  {
    type: 'thinking',
    content: 'Now I should look for information about climate solutions'
  },
  {
    type: 'tool_call',
    content: 'Searching for climate change solutions',
    tool: 'web-search',
    query: 'effective climate change solutions 2023'
  }
];

const sampleClarifyingQuestions = [
  'Are you more interested in temperature trends or extreme weather events?',
  'Would you like to focus on global data or a specific region?',
  'Are you looking for individual actions or policy-level solutions?'
];

/**
 * TestComponents - A component to showcase different UI elements for testing
 */
const TestComponents: React.FC = () => {
  const theme = useTheme();
  const [tabValue, setTabValue] = useState(0);
  const [clarificationAnswer, setClarificationAnswer] = useState<string>('');

  // Format timestamp to 24-hour format without seconds
  const formatTimestamp = (timestamp?: Date): string => {
    if (!timestamp) return '';
    const date = new Date(timestamp);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
  };

  // Handle tab change
  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setTabValue(newValue);
  };

  // Handle clarification submit
  const handleClarificationSubmit = (answer: string) => {
    setClarificationAnswer(answer);
    console.log('Clarification submitted:', answer);
  };

  // Render a regular message
  const renderMessage = (message: any) => {
    const isUserMessage = message.role === 'user';
    const isAssistantMessage = message.role === 'assistant';
    
    const bgColor = isUserMessage
      ? theme.palette.mode === 'dark'
        ? alpha(theme.palette.primary.dark, 0.15)
        : alpha(theme.palette.primary.light, 0.15)
      : isAssistantMessage
      ? theme.palette.mode === 'dark'
        ? alpha(theme.palette.secondary.dark, 0.15)
        : alpha(theme.palette.secondary.light, 0.15)
      : theme.palette.background.default;

    return (
      <Box
        key={message.id}
        sx={{
          width: '100%',
          display: 'flex',
          justifyContent: isUserMessage ? 'flex-end' : 'flex-start',
          marginBottom: 2,
        }}
      >
        <Box
          sx={{
            maxWidth: '80%',
            padding: 2,
            borderRadius: 2,
            backgroundColor: bgColor,
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', marginBottom: 1 }}>
            <Typography variant="caption" fontWeight="bold" color="text.secondary">
              {message.role === 'user'
                ? 'You'
                : message.role === 'assistant'
                ? 'Denker'
                : 'System'}
            </Typography>
            {message.timestamp && (
              <Typography
                variant="caption"
                color="text.secondary"
                sx={{ ml: 1 }}
              >
                {formatTimestamp(message.timestamp)}
              </Typography>
            )}
          </Box>
          
          <Typography
            variant="body2"
            sx={{
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
            }}
          >
            {message.content}
          </Typography>
        </Box>
      </Box>
    );
  };

  // Render a streaming steps message
  const renderStreamingSteps = () => {
    // Format streaming steps with emoji prefixes
    const formattedContent = sampleStreamingSteps.map(step => {
      switch (step.type) {
        case 'thinking':
          return `💭 ${step.content}`;
        case 'tool_call':
          return `🔍 Using ${step.tool} to search: "${step.query}"`;
        case 'result':
          return `🌐 ${step.source === 'web' ? 'Web' : 'Document'} search result: ${step.content}`;
        default:
          return `⚙️ ${step.type}: ${step.content}`;
      }
    }).join('\n\n');

    const streamingMessage = {
      id: 'stream_123',
      content: `⚙️ Processing request...\n\n${formattedContent}`,
      role: 'assistant',
      timestamp: new Date(),
      metadata: { isProcessing: true }
    };

    return renderMessage(streamingMessage);
  };

  return (
    <Container maxWidth="md" sx={{ py: 4 }}>
      <Typography variant="h4" gutterBottom>
        UI Test Components
      </Typography>
      <Typography variant="body1" paragraph>
        This page shows different UI components used in the chat interface for testing purposes without needing a backend connection.
      </Typography>

      <Tabs value={tabValue} onChange={handleTabChange} sx={{ mb: 3 }}>
        <Tab label="Regular Messages" />
        <Tab label="Streaming Steps" />
        <Tab label="Clarification UI" />
        <Tab label="All Together" />
      </Tabs>

      <Paper sx={{ p: 3, mb: 4 }}>
        {tabValue === 0 && (
          <>
            <Typography variant="h6" gutterBottom>
              Regular Assistant Messages
            </Typography>
            <Typography variant="body2" paragraph color="text.secondary">
              These are the standard message bubbles shown in the chat area.
            </Typography>
            <Box sx={{ mt: 3 }}>
              {sampleMessages.map(message => renderMessage(message))}
            </Box>
          </>
        )}

        {tabValue === 1 && (
          <>
            <Typography variant="h6" gutterBottom>
              Streaming Steps Message
            </Typography>
            <Typography variant="body2" paragraph color="text.secondary">
              This shows how intermediate thinking/processing steps appear in the UI with special formatting.
            </Typography>
            <Box sx={{ mt: 3 }}>
              {renderStreamingSteps()}
            </Box>
          </>
        )}

        {tabValue === 2 && (
          <>
            <Typography variant="h6" gutterBottom>
              Clarification UI
            </Typography>
            <Typography variant="body2" paragraph color="text.secondary">
              This is the special UI shown when the agent needs additional information.
            </Typography>
            <Box sx={{ mt: 3 }}>
              <ClarificationPrompt 
                questions={sampleClarifyingQuestions} 
                onSubmit={handleClarificationSubmit}
              />
              
              {clarificationAnswer && (
                <Paper sx={{ p: 2, mt: 2, bgcolor: 'success.light' }}>
                  <Typography variant="subtitle1" color="white">
                    Clarification Submitted:
                  </Typography>
                  <Typography variant="body2" color="white">
                    {clarificationAnswer}
                  </Typography>
                </Paper>
              )}
            </Box>
          </>
        )}

        {tabValue === 3 && (
          <>
            <Typography variant="h6" gutterBottom>
              Complete Conversation Flow
            </Typography>
            <Typography variant="body2" paragraph color="text.secondary">
              This shows how a complete conversation might look with all elements.
            </Typography>
            
            <Box sx={{ mt: 3 }}>
              {/* User question */}
              {renderMessage(sampleMessages[0])}
              
              {/* Assistant response */}
              {renderMessage(sampleMessages[1])}
              
              {/* Second user question */}
              {renderMessage(sampleMessages[2])}
              
              {/* Streaming steps for processing */}
              {renderStreamingSteps()}
              
              {/* Clarification UI */}
              <Box sx={{ p: 2 }}>
                <ClarificationPrompt 
                  questions={sampleClarifyingQuestions} 
                  onSubmit={handleClarificationSubmit}
                />
              </Box>
              
              {clarificationAnswer && (
                <>
                  {/* User's clarification response */}
                  {renderMessage({
                    id: 'user_clarification',
                    content: clarificationAnswer,
                    role: 'user',
                    timestamp: new Date()
                  })}
                  
                  {/* Final assistant response */}
                  {renderMessage({
                    id: 'assistant_final',
                    content: `Based on your clarification that "${clarificationAnswer}", I can provide more specific information.\n\nRecent climate data shows that global temperatures increased by 1.2°C compared to pre-industrial levels. Extreme weather events like hurricanes and wildfires have become more frequent and severe.\n\nFor solutions, a combination of policy changes and individual actions can make a difference. Renewable energy adoption is accelerating, with solar and wind power becoming more affordable.`,
                    role: 'assistant',
                    timestamp: new Date()
                  })}
                </>
              )}
            </Box>
          </>
        )}
      </Paper>
    </Container>
  );
};

export default TestComponents; 