import React, { useEffect, useRef, useState, useCallback } from 'react';
import { Box, Typography, CircularProgress, Paper, Divider, useTheme, IconButton, Tooltip, Fab } from '@mui/material';
import DownloadIcon from '@mui/icons-material/Download';
import DeleteIcon from '@mui/icons-material/Delete';
import InsertDriveFileIcon from '@mui/icons-material/InsertDriveFile';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import PersonIcon from '@mui/icons-material/Person';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import ErrorIcon from '@mui/icons-material/Error';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ArrowDownwardIcon from '@mui/icons-material/ArrowDownward';
import { alpha } from '@mui/material/styles';

// Utilities for rendering message content
import { marked } from 'marked';
import { useMainWindowHooks } from '../../hooks';
import { Message } from '../../types/types';
import { FileAttachment } from '../../hooks/conversation/types';
import ClarificationPrompt from '../ClarificationPrompt';
import HumanInputPrompt from '../HumanInputPrompt';
import { ChatFileSystemActivity } from '../FileSystem';
import { HumanInputRequest } from '../../hooks/conversation/useRealTimeUpdates';
import AgentStatusIndicator from '../AgentStatusIndicator';

// Configure marked renderer for secure and styled markdown rendering
marked.setOptions({
  breaks: true,
  gfm: true
});

// --- ADDED: Override link rendering ---
const renderer = new marked.Renderer();
const originalLinkRenderer = renderer.link;
renderer.link = (href, title, text) => {
  let html = originalLinkRenderer.call(renderer, href, title, text);
  // Add target="_blank" and rel="noopener noreferrer" to external links
  // Simple check: assume http/https links are external
  if (href && href.startsWith('http')) {
    html = html.replace(/^<a /, '<a target="_blank" rel="noopener noreferrer" ');
  }
  return html;
};
// --- END ADDED ---

// Types
interface ChatAreaProps {
  messages: Message[];
  isLoading: boolean;
  isLoadingMore: boolean;
  hasMoreMessages: boolean;
  loadMoreMessages: () => void;
  humanInputRequest?: HumanInputRequest | null;
  onHumanInputSubmit?: (input: string) => void;
  onHumanInputCancel?: () => void;
}

/**
 * ChatArea component renders the conversation messages and handles scrolling
 */
const ChatAreaNew: React.FC<ChatAreaProps> = ({ 
  messages, 
  isLoading, 
  isLoadingMore,
  hasMoreMessages,
  loadMoreMessages,
  humanInputRequest,
  onHumanInputSubmit,
  onHumanInputCancel
}) => {
  const theme = useTheme();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const [expandedMessage, setExpandedMessage] = useState<string | null>(null);
  const [showScrollDownButton, setShowScrollDownButton] = useState(false);
  const [isNearTop, setIsNearTop] = useState(false);
  const [userHasScrolledUp, setUserHasScrolledUp] = useState(false);
  
  // Refs to store scroll position before loading more messages
  const scrollInfoBeforeLoad = useRef<{ scrollTop: number; scrollHeight: number } | null>(null);
  
  // Track previous message count to detect initial load
  const prevMessageCountRef = useRef(0);
  
  // Log messages for debugging
  useEffect(() => {
    console.log('🔍 ChatAreaNew rendering with:', {
      messageCount: messages.length,
      isLoading,
      isLoadingMore,
      hasMoreMessages,
      messageIds: messages.map(m => m.id.substring(0, 8) + '...'),
      messageRoles: messages.map(m => m.role),
      firstCharacters: messages.map(m => typeof m.content === 'string' ? 
        `${m.content.substring(0, 20)}...` : 
        '[complex content]')
    });
  }, [messages, isLoading, isLoadingMore, hasMoreMessages]);
  
  // Get file actions from hooks
  const { file } = useMainWindowHooks();
  
  // Scroll to bottom function
  const scrollToBottom = useCallback((behavior: ScrollBehavior = 'smooth') => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: behavior });
    }
  }, []);

  // Scroll to bottom when new messages are added, unless user scrolled up
  useEffect(() => {
    const container = scrollContainerRef.current;
    if (!container) return;

    // Only scroll if the user hasn't manually scrolled up
    if (!userHasScrolledUp) {
      console.log("[Scroll Debug] Messages changed and user hasn't scrolled up, scheduling instant scroll.");
      // Use setTimeout to ensure DOM has updated after message addition
      setTimeout(() => scrollToBottom('instant'), 0);
    } else {
      console.log("[Scroll Debug] Messages changed, but user has scrolled up. No auto-scroll.");
    }

    // This effect strictly depends on the messages array changing
  }, [messages, scrollToBottom, userHasScrolledUp]);
  
  // Handle scroll events to show/hide the scroll-down button and trigger loading more
  const handleScroll = useCallback(() => {
    const container = scrollContainerRef.current;
    if (container) {
      const { scrollTop, scrollHeight, clientHeight } = container;
      // Scroll down button logic
      const threshold = 100; // Pixels from bottom to hide button
      const isNearBottom = scrollHeight - scrollTop - clientHeight < threshold;
      setShowScrollDownButton(!isNearBottom);
      
      // Update userHasScrolledUp state based on position
      // Use a slightly larger threshold for deciding if user scrolled away
      const scrollAwayThreshold = 150; 
      if (scrollHeight - scrollTop - clientHeight >= scrollAwayThreshold && !userHasScrolledUp) {
        // User scrolled up sufficiently
        setUserHasScrolledUp(true);
        console.log("[Scroll State] User scrolled up.");
      } else if (isNearBottom && userHasScrolledUp) {
        // User scrolled back down
        setUserHasScrolledUp(false);
        console.log("[Scroll State] User scrolled back to bottom.");
      }
      
      // Load more messages logic
      const topThreshold = 50; // Pixels from top to trigger load
      const nearTop = scrollTop < topThreshold;
      setIsNearTop(nearTop);
      
      if (nearTop && !isLoadingMore && hasMoreMessages) {
        console.log('📜 Scroll near top, attempting to load more messages...');
        // Store scroll position BEFORE loading starts
        scrollInfoBeforeLoad.current = {
          scrollTop: scrollTop,
          scrollHeight: scrollHeight,
        };
        loadMoreMessages();
      }
    } else {
      setShowScrollDownButton(false);
      setIsNearTop(false);
    }
  }, [isLoadingMore, hasMoreMessages, loadMoreMessages]);

  // Add/remove scroll listener
  useEffect(() => {
    const container = scrollContainerRef.current;
    if (container) {
      container.addEventListener('scroll', handleScroll);
      // Initial check in case it loads scrolled up
      handleScroll(); 
      return () => container.removeEventListener('scroll', handleScroll);
    }
  }, [handleScroll]);
  
  // Format file size
  const formatFileSize = (bytes?: number): string => {
    if (!bytes) return '';
    if (bytes < 1024) return bytes + ' B';
    else if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
    else return (bytes / 1048576).toFixed(1) + ' MB';
  };
  
  // Render the attachments for a message
  const renderAttachments = (files?: any[]) => {
    if (!files || files.length === 0) return null;

    return (
      <Box sx={{ mb: 1 }}>
        {files.map((attachment, idx) => {
          const fileName = attachment.name || attachment.file?.name || 'Unknown file';
          const fileSize = attachment.size || attachment.file?.size || 0;
          const fileId = attachment.id || `file-${idx}`;
          const hasError = attachment.hasError || false;
          const isUploading = attachment.isUploading || false;
          const isDeleted = attachment.isDeleted || false;
          
          const iconColor = hasError 
            ? theme.palette.error.main 
            : theme.palette.primary.main;
            
          return (
            <Paper
              key={fileId}
              variant="outlined"
              sx={{
                p: 1,
                mb: 0.5,
                display: 'flex',
                alignItems: 'center',
                opacity: isDeleted ? 0.5 : 1,
                bgcolor: 'background.paper',
              }}
            >
              {hasError ? (
                <Tooltip title="Error uploading file">
                  <ErrorIcon sx={{ color: theme.palette.error.main, mr: 1 }} />
                </Tooltip>
              ) : isUploading ? (
                <CircularProgress size={20} sx={{ mr: 1 }} />
              ) : (
                <Tooltip title="File attached">
                  <CheckCircleIcon sx={{ color: iconColor, mr: 1 }} />
                </Tooltip>
              )}
              <Typography variant="body2" noWrap>
                {fileName} {fileSize > 0 && `(${formatFileSize(fileSize)})`}
              </Typography>
            </Paper>
          );
        })}
      </Box>
    );
  };
  
  // Format timestamp to 24-hour format without seconds
  const formatTimestamp = (timestamp?: Date): string => {
    if (!timestamp) return '';
    const date = new Date(timestamp);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
  };
  
  // Render a single message
  const renderMessage = (message: Message, index: number) => {
    const isUserMessage = message.role === 'user';
    const isAssistantMessage = message.role === 'assistant';
    const isSystemMessage = message.role === 'system';
    
    // Determine background color based on message role
    let bgColor;
    if (isUserMessage) {
      bgColor = theme.palette.mode === 'dark'
        ? alpha(theme.palette.primary.dark, 0.15)
        : alpha(theme.palette.primary.light, 0.15);
    } else if (isAssistantMessage) {
      bgColor = theme.palette.mode === 'dark'
        ? alpha(theme.palette.secondary.dark, 0.15)
        : alpha(theme.palette.secondary.light, 0.15);
    } else if (isSystemMessage) {
      bgColor = theme.palette.mode === 'dark'
        ? alpha(theme.palette.grey[700], 0.2)
        : alpha(theme.palette.grey[300], 0.2);
    } else {
      bgColor = theme.palette.background.default;
    }

    // --- MODIFIED: Only check message.files --- 
    const attachmentsToRender = message.files; // Only use message.files
    const hasAttachments = attachmentsToRender && attachmentsToRender.length > 0;
    // --- END MODIFICATION ---
    
    // Define standard message width
    const messageWidth = '90%'; // Use consistent width
    
    return (
      <Box
        key={message.id || index}
        sx={{
          width: '100%',
          display: 'flex',
          justifyContent: isUserMessage ? 'flex-end' : 'flex-start',
          marginBottom: 2, // Consistent margin
        }}
      >
        <Box
          sx={{
            maxWidth: messageWidth,
            padding: 1.5, // Reduced padding
            borderRadius: 2,
            backgroundColor: bgColor,
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', marginBottom: 1 }}>
            <Typography 
              variant="caption" 
              fontWeight="bold" 
              color={"text.secondary"} // Consistent label color
            >
              {message.role === 'user'
                ? 'You'
                : message.role === 'assistant'
                ? 'Denker'
                : (message.metadata?.agent || 'System') // Display agent name or fallback to System
              }
            </Typography>
            {message.metadata?.stepType && (
              <Typography
                variant="caption"
                color="text.secondary" // Use secondary color for step type
                sx={{ ml: 1, fontStyle: 'italic' }}
              >
                {message.metadata.stepType}
              </Typography>
            )}
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
          
          {hasAttachments && renderAttachments(attachmentsToRender)}
          
          {/* Render content using marked for markdown support */}
          <Box
            component="div" // Use a div to render HTML
            sx={{
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
              lineHeight: '1 !important', // Force minimum line height
              fontFamily: 'inherit', // Use default font
              ...(theme.typography.body2),
              '& p': {
                marginTop: '0.2em', // Further reduce paragraph margins
                marginBottom: '0.2em',
              },
              '& h1, & h2, & h3, & h4, & h5, & h6': {
                marginTop: '0.2em', 
                marginBottom: '0.2em',
              },
              '& ul, & ol': {
                marginTop: '0.2em',
                marginBottom: '0.2em',
                paddingLeft: '2em', // Keep standard list indentation
              },
              '& li': {
                marginTop: '0.1em',
                marginBottom: '0.1em',
              },
              '& h1': { fontSize: '1.5em' }, // Example size adjustments
              '& h2': { fontSize: '1.3em' },
              '& h3': { fontSize: '1.15em' },
              '& h4, & h5, & h6': { fontSize: '1em' }, // Keep smaller headings closer to base size
              '& a': {
                color: theme.palette.primary.main, 
                textDecoration: 'underline',
              },
              '& code': {
                backgroundColor: alpha(theme.palette.text.primary, 0.1),
                padding: '0.1em 0.3em',
                borderRadius: '4px',
                fontSize: '0.9em',
              },
              '& pre': {
                backgroundColor: alpha(theme.palette.text.primary, 0.1),
                padding: theme.spacing(1),
                borderRadius: '4px',
                overflowX: 'auto',
              }
            }}
            dangerouslySetInnerHTML={{
              __html: message.content ? marked(message.content, { renderer }) : '<i style="color: grey;">No content</i>' // Use the custom renderer
            }}
          />
          
          {/* Add filesystem activity display for assistant messages */}
          {isAssistantMessage && (
            <ChatFileSystemActivity messageId={message.id} />
          )}
        </Box>
      </Box>
    );
  };
  
  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        flexGrow: 1,
        overflow: 'hidden',
        backgroundColor: theme.palette.background.default,
        position: 'relative',
      }}
    >
      <Box
        ref={scrollContainerRef} 
        sx={{
          flexGrow: 1,
          overflow: 'auto',
          display: 'flex',
          flexDirection: 'column',
          padding: 2,
        }}
      >
        {messages.length === 0 && !isLoading ? (
          <Box
            sx={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              height: '100%',
              textAlign: 'center',
              px: 3,
            }}
          >
            <Box
              sx={{
                width: 60,
                height: 60,
                borderRadius: '50%',
                backgroundColor: theme.palette.primary.main,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                mb: 2,
                fontSize: '30px',
                color: '#fff',
                fontWeight: 'bold',
                opacity: 0.8
              }}
            >
              D
            </Box>
            <Typography variant="h6">
              Welcome to Denker
            </Typography>
            <Typography variant="body2" color="textSecondary" sx={{ mt: 1, maxWidth: 600 }}>
              Start a conversation by typing a message below. You can ask questions, 
              request information, or upload files for analysis.
            </Typography>
          </Box>
        ) : (
          <>
            {messages.map((message, index) => renderMessage(message, index))}
            
            {/* Ref should be after messages but before loading/prompts */}
            <div ref={messagesEndRef} />
            
            {/* Show human input prompt if needed */}
            {humanInputRequest && onHumanInputSubmit && (
              <Box sx={{ p: 2 }}>
                <HumanInputPrompt 
                  toolName={humanInputRequest.toolName}
                  inputPrompt={humanInputRequest.inputPrompt}
                  toolDescription={humanInputRequest.toolDescription}
                  onSubmit={onHumanInputSubmit}
                  onCancel={onHumanInputCancel}
                />
              </Box>
            )}
            
            {isLoading && (
              <Box
                sx={{
                  display: 'flex',
                  justifyContent: 'center',
                  p: 2,
                }}
              >
                <CircularProgress size={24} />
              </Box>
            )}
          </>
        )}
      </Box>

      {/* Conditionally render Scroll Down Button */} 
      {showScrollDownButton && !isLoadingMore && (
          <Fab 
            size="small" 
            color="primary" 
            aria-label="scroll down"
            onClick={() => scrollToBottom('smooth')}
            sx={{
                position: 'absolute',
                bottom: '20px', // Position above status indicator/input
                right: '20px',
                zIndex: 1050, // Below status indicator potentially
            }}
          >
              <ArrowDownwardIcon />
          </Fab>
      )}
    </Box>
  );
};

export default ChatAreaNew; 