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
import SearchIcon from '@mui/icons-material/Search';
import ArticleIcon from '@mui/icons-material/Article';
import EditIcon from '@mui/icons-material/Edit';
import AddIcon from '@mui/icons-material/Add';
import ImageIcon from '@mui/icons-material/Image';
import BarChartIcon from '@mui/icons-material/BarChart';
import FolderIcon from '@mui/icons-material/Folder';
import FileCopyIcon from '@mui/icons-material/FileCopy';
import StorageIcon from '@mui/icons-material/Storage';
import MemoryIcon from '@mui/icons-material/Memory';
import WebIcon from '@mui/icons-material/Web';
import CodeIcon from '@mui/icons-material/Code';
import SettingsIcon from '@mui/icons-material/Settings';
import FunctionsIcon from '@mui/icons-material/Functions';
import VisibilityIcon from '@mui/icons-material/Visibility';
import CreateIcon from '@mui/icons-material/Create';
import DashboardIcon from '@mui/icons-material/Dashboard';
import PieChartIcon from '@mui/icons-material/PieChart';
import ListIcon from '@mui/icons-material/List';
import InfoIcon from '@mui/icons-material/Info';
import DriveFileMoveIcon from '@mui/icons-material/DriveFileMove';
import FolderOpenIcon from '@mui/icons-material/FolderOpen';
import FindInPageIcon from '@mui/icons-material/FindInPage';
import CreateNewFolderIcon from '@mui/icons-material/CreateNewFolder';
import DescriptionIcon from '@mui/icons-material/Description';
import PictureAsPdfIcon from '@mui/icons-material/PictureAsPdf';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import ReadMoreIcon from '@mui/icons-material/ReadMore';
import PostAddIcon from '@mui/icons-material/PostAdd';
import TransformIcon from '@mui/icons-material/Transform';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import PublicIcon from '@mui/icons-material/Public';
import TravelExploreIcon from '@mui/icons-material/TravelExplore';
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

// Type declaration for window object
declare global {
  interface Window {
    electron?: {
      openFile: (filePath?: string) => Promise<{ success: boolean; error?: string } | void>;
    };
    openFileInSystem: (filePath: string) => Promise<void>;
    openImageInBrowser: (imagePath: string) => void;
  }
}

// --- ADDED: Override link and image rendering ---
const renderer = new marked.Renderer();

// Function to detect if a string looks like a file path
const isFilePath = (text: string): boolean => {
  const trimmedText = text.trim();
  
  // Skip very short strings or obviously not file paths
  if (trimmedText.length < 3 || trimmedText.includes(' ')) {
    return false;
  }
  
  // Check for common file path patterns
  const filePathPatterns = [
    // Absolute Unix/Mac paths - simplified to be more inclusive
    /^\/.*\.(md|txt|json|py|js|ts|tsx|jsx|html|css|scss|sass|less|png|jpg|jpeg|gif|svg|pdf|doc|docx|xls|xlsx|ppt|pptx|zip|tar|gz|csv|xml|yaml|yml|toml|ini|cfg|conf|log)$/i,
    // Windows absolute paths
    /^[A-Za-z]:\\[^\\]*.*\.(md|txt|json|py|js|ts|tsx|jsx|html|css|scss|sass|less|png|jpg|jpeg|gif|svg|pdf|doc|docx|xls|xlsx|ppt|pptx|zip|tar|gz|csv|xml|yaml|yml|toml|ini|cfg|conf|log)$/i,
    // Relative paths starting with ./ or ../
    /^\.\.?\/.*\.(md|txt|json|py|js|ts|tsx|jsx|html|css|scss|sass|less|png|jpg|jpeg|gif|svg|pdf|doc|docx|xls|xlsx|ppt|pptx|zip|tar|gz|csv|xml|yaml|yml|toml|ini|cfg|conf|log)$/i,
    // Home directory paths
    /^~\/.*\.(md|txt|json|py|js|ts|tsx|jsx|html|css|scss|sass|less|png|jpg|jpeg|gif|svg|pdf|doc|docx|xls|xlsx|ppt|pptx|zip|tar|gz|csv|xml|yaml|yml|toml|ini|cfg|conf|log)$/i,
    // Simple filename with extension (be more selective to avoid false positives)
    /^[a-zA-Z0-9_\-\.]+\.(md|txt|json|py|js|ts|tsx|jsx|html|css|scss|sass|less|png|jpg|jpeg|gif|svg|pdf|doc|docx|xls|xlsx|ppt|pptx|zip|tar|gz|csv|xml|yaml|yml|toml|ini|cfg|conf|log)$/i,
    // Common document patterns without path separators
    /^[a-zA-Z0-9_\-\.]+\.(pdf|docx?|xlsx?|pptx?)$/i,
  ];
  
  // Additional check: must contain path separators or be a simple filename
  const hasPathSeparators = trimmedText.includes('/') || trimmedText.includes('\\');
  const isSimpleFilename = /^[a-zA-Z0-9_\-\.]+\.[a-zA-Z0-9]+$/i.test(trimmedText);
  
  const isMatch = filePathPatterns.some(pattern => pattern.test(trimmedText)) && (hasPathSeparators || isSimpleFilename);
  
  // Debug logging
  if (isMatch) {
    console.log(`[FilePath] Detected file path: "${trimmedText}"`);
  }
  
  return isMatch;
};

// Function to open file in system
const openFileInSystem = async (filePath: string) => {
  try {
    // Use the Electron API if available - FIXED: Use window.electron instead of window.electronAPI
    if (window.electron?.openFile) {
      console.log(`[FilePath] Opening file via Electron API: ${filePath}`);
      const result = await window.electron.openFile(filePath);
      
      if (result && !result.success) {
        throw new Error(result.error || 'Failed to open file');
      }
      
      console.log(`[FilePath] Successfully opened file: ${filePath}`);
    } else {
      console.warn('[FilePath] Electron API not available, falling back to browser method');
      // Fallback: try to open via browser (for web version)
      // This will attempt to download/open the file
      const link = document.createElement('a');
      link.href = filePath;
      link.target = '_blank';
      link.click();
    }
  } catch (error) {
    console.error('Failed to open file:', error);
    // Show user-friendly error
    const errorMessage = error instanceof Error ? error.message : 'Unknown error occurred';
    alert(`Could not open file: ${filePath}\n\nError: ${errorMessage}\n\nTip: Make sure the file exists and you have permission to access it.`);
  }
};

// Expose function globally for onclick handlers
window.openFileInSystem = openFileInSystem;

// Function to open image in browser
const openImageInBrowser = (imagePath: string) => {
  try {
    const link = document.createElement('a');
    link.href = imagePath;
    link.target = '_blank';
    link.click();
  } catch (error) {
    console.error('Failed to open image:', error);
  }
};

// Expose image function globally
window.openImageInBrowser = openImageInBrowser;

// Override text rendering to detect and make file paths clickable
const originalTextRenderer = renderer.text;
renderer.text = (text) => {
  // First check if the entire text is a file path
  if (isFilePath(text)) {
    console.log(`[FilePath] Rendering clickable path: "${text}"`);
    return `<span 
      class="clickable-file-path" 
      onclick="window.openFileInSystem('${text.replace(/'/g, "\\'")}')"
      style="
        color: #1976d2 !important; 
        cursor: pointer; 
        text-decoration: underline;
        font-family: monospace;
        background-color: rgba(25, 118, 210, 0.1);
        padding: 2px 4px;
        border-radius: 3px;
        transition: all 0.2s ease;
        border: 1px solid rgba(25, 118, 210, 0.2);
      "
      onmouseover="this.style.backgroundColor='rgba(25, 118, 210, 0.2)'; this.style.borderColor='rgba(25, 118, 210, 0.4)'"
      onmouseout="this.style.backgroundColor='rgba(25, 118, 210, 0.1)'; this.style.borderColor='rgba(25, 118, 210, 0.2)'"
      title="Click to open file: ${text}"
    >${text}</span>`;
  }
  
  // If not, check for file paths embedded within the text
  const filePathRegex = /([\/~](?:[a-zA-Z0-9_\-\.\/\\]+)\.(?:md|txt|json|py|js|ts|tsx|jsx|html|css|scss|sass|less|png|jpg|jpeg|gif|svg|pdf|doc|docx|xls|xlsx|ppt|pptx|zip|tar|gz|csv|xml|yaml|yml|toml|ini|cfg|conf|log))(?=\s|$|[^\w\-\.])/gi;
  
  if (filePathRegex.test(text)) {
    console.log(`[FilePath] Found embedded file paths in text: "${text}"`);
    // Reset regex for replacement
    filePathRegex.lastIndex = 0;
    const processedText = text.replace(filePathRegex, (match, filePath) => {
      console.log(`[FilePath] Making embedded path clickable: "${filePath}"`);
      return `<span 
        class="clickable-file-path" 
        onclick="window.openFileInSystem('${filePath.replace(/'/g, "\\'")}')"
        style="
          color: #1976d2 !important; 
          cursor: pointer; 
          text-decoration: underline;
          font-family: monospace;
          background-color: rgba(25, 118, 210, 0.1);
          padding: 2px 4px;
          border-radius: 3px;
          transition: all 0.2s ease;
          border: 1px solid rgba(25, 118, 210, 0.2);
        "
        onmouseover="this.style.backgroundColor='rgba(25, 118, 210, 0.2)'; this.style.borderColor='rgba(25, 118, 210, 0.4)'"
        onmouseout="this.style.backgroundColor='rgba(25, 118, 210, 0.1)'; this.style.borderColor='rgba(25, 118, 210, 0.2)'"
        title="Click to open file: ${filePath}"
      >${filePath}</span>`;
    });
    return processedText;
  }
  
  // For non-file-path text, use original renderer
  return originalTextRenderer.call(renderer, text);
};

// Override code rendering to also detect file paths in code blocks
const originalCodeRenderer = renderer.code;
renderer.code = (code: string, infostring: string | undefined, escaped: boolean) => {
  const trimmedCode = code.trim();
  
  // Check if the entire code block is a file path
  if (isFilePath(trimmedCode)) {
    console.log(`[FilePath] Rendering clickable code path: "${trimmedCode}"`);
    return `<span 
      class="clickable-file-path" 
      onclick="window.openFileInSystem('${trimmedCode.replace(/'/g, "\\'")}')"
      style="
        color: #1976d2 !important; 
        cursor: pointer; 
        text-decoration: underline;
        font-family: monospace;
        background-color: rgba(25, 118, 210, 0.1);
        padding: 4px 8px;
        border-radius: 4px;
        transition: all 0.2s ease;
        display: inline-block;
        border: 1px solid rgba(25, 118, 210, 0.2);
      "
      onmouseover="this.style.backgroundColor='rgba(25, 118, 210, 0.2)'; this.style.borderColor='rgba(25, 118, 210, 0.4)'"
      onmouseout="this.style.backgroundColor='rgba(25, 118, 210, 0.1)'; this.style.borderColor='rgba(25, 118, 210, 0.2)'"
      title="Click to open file: ${trimmedCode}"
    >${trimmedCode}</span>`;
  }
  
  // For non-file-path code, check if it contains file paths on individual lines
  const lines = code.split('\n');
  let hasFilePaths = false;
  const processedLines = lines.map(line => {
    const trimmedLine = line.trim();
    if (isFilePath(trimmedLine)) {
      hasFilePaths = true;
      return `<span 
        class="clickable-file-path" 
        onclick="window.openFileInSystem('${trimmedLine.replace(/'/g, "\\'")}')"
        style="
          color: #1976d2 !important; 
          cursor: pointer; 
          text-decoration: underline;
          font-family: monospace;
          background-color: rgba(25, 118, 210, 0.1);
          padding: 1px 3px;
          border-radius: 2px;
          transition: all 0.2s ease;
          border: 1px solid rgba(25, 118, 210, 0.2);
        "
        onmouseover="this.style.backgroundColor='rgba(25, 118, 210, 0.2)'"
        onmouseout="this.style.backgroundColor='rgba(25, 118, 210, 0.1)'"
        title="Click to open file: ${trimmedLine}"
      >${trimmedLine}</span>`;
    }
    return line;
  });
  
  if (hasFilePaths) {
    return `<pre><code>${processedLines.join('\n')}</code></pre>`;
  }
  
  // For non-file-path code, use original renderer
  return originalCodeRenderer.call(renderer, code, infostring, escaped);
};

// Override link rendering for external links
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

// Override image rendering for size constraints and click functionality
const originalImageRenderer = renderer.image;
renderer.image = (href, title, text) => {
  const altText = text || 'Image';
  const titleAttr = title ? ` title="${title}"` : '';
  return `<img 
    src="${href}" 
    alt="${altText}"${titleAttr}
    class="message-image" 
    onclick="window.openImageInBrowser('${href}')"
    style="
      max-width: 100%; 
      max-height: 300px; 
      object-fit: contain; 
      cursor: pointer; 
      border-radius: 8px; 
      box-shadow: 0 2px 8px rgba(0,0,0,0.1);
      transition: all 0.2s ease;
    "
    onmouseover="this.style.transform='scale(1.02)'; this.style.boxShadow='0 4px 16px rgba(0,0,0,0.15)'"
    onmouseout="this.style.transform='scale(1)'; this.style.boxShadow='0 2px 8px rgba(0,0,0,0.1)'"
  />`;
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
  const [expandedToolCalls, setExpandedToolCalls] = useState<Set<string>>(new Set());
  const [showScrollDownButton, setShowScrollDownButton] = useState(false);
  const [isNearTop, setIsNearTop] = useState(false);
  const [userHasScrolledUp, setUserHasScrolledUp] = useState(false);
  
  // Note: Image popup removed - now opens in external browser
  
  // Refs to store scroll position before loading more messages
  const scrollInfoBeforeLoad = useRef<{ scrollTop: number; scrollHeight: number } | null>(null);
  
  // Track previous message count to detect initial load
  const prevMessageCountRef = useRef(0);
  
  // Set up global function for opening image in browser
  useEffect(() => {
    // @ts-ignore
    window.openImageInBrowser = (src: string) => {
      // Open image in external browser
      // @ts-ignore
      if (window.electron?.shell?.openExternal) {
        // @ts-ignore
        window.electron.shell.openExternal(src);
      } else {
        // Fallback for web version
        window.open(src, '_blank', 'noopener,noreferrer');
      }
    };
    
    return () => {
      // @ts-ignore
      delete window.openImageInBrowser;
    };
  }, []);
  
  // Add CSS animations for tool call messages
  useEffect(() => {
    const style = document.createElement('style');
    style.textContent = `
      @keyframes toolCallShimmer {
        0% {
          left: -100%;
          opacity: 0;
        }
        50% {
          opacity: 1;
        }
        100% {
          left: 100%;
          opacity: 0;
        }
      }
    `;
    document.head.appendChild(style);
    
    return () => {
      document.head.removeChild(style);
    };
  }, []);
  
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
  
  // Debounce ref for load more attempts to prevent excessive API calls
  const loadMoreDebounceRef = useRef<NodeJS.Timeout | null>(null);
  const lastLoadAttemptRef = useRef<number>(0);
  
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
      
      // Load more messages logic - with efficiency improvements
      const topThreshold = 50; // Pixels from top to trigger load
      const nearTop = scrollTop < topThreshold;
      setIsNearTop(nearTop);
      
      // ENHANCED DEBUG LOGGING
      if (nearTop) {
        console.log('🔍 SCROLL DEBUG - Near top detected:', {
          scrollTop,
          nearTop,
          isLoadingMore,
          hasMoreMessages,
          messagesLength: messages.length,
          scrollHeight,
          clientHeight
        });
      }
      
      // Enhanced efficiency checks before attempting to load more
      if (nearTop && !isLoadingMore && hasMoreMessages) {
        // Additional efficiency checks
        const now = Date.now();
        const timeSinceLastAttempt = now - lastLoadAttemptRef.current;
        const hasMessages = messages.length > 0;
        
        console.log('🔍 SCROLL DEBUG - Load more conditions:', {
          nearTop: true,
          isLoadingMore: false,
          hasMoreMessages: true,
          timeSinceLastAttempt,
          hasMessages,
          scrollTop,
          willAttemptLoad: timeSinceLastAttempt >= 1000 && hasMessages && scrollTop > 0
        });
        
        // Don't attempt if:
        // 1. We tried very recently (< 1 second ago)
        // 2. We have no messages (nothing to paginate from)
        if (timeSinceLastAttempt < 1000) {
          console.log('📜 Load more skipped - too recent attempt');
          return;
        }
        
        if (!hasMessages) {
          console.log('📜 Load more skipped - no messages to paginate from');
          return;
        }
        
        // Clear any existing debounce
        if (loadMoreDebounceRef.current) {
          clearTimeout(loadMoreDebounceRef.current);
        }
        
        // Debounce the load attempt
        loadMoreDebounceRef.current = setTimeout(() => {
          console.log('🚀 SCROLL DEBUG - Triggering loadMoreMessages!');
          lastLoadAttemptRef.current = Date.now();
          
          // Store scroll position BEFORE loading starts
          scrollInfoBeforeLoad.current = {
            scrollTop: scrollTop,
            scrollHeight: scrollHeight,
          };
          loadMoreMessages();
        }, 300); // 300ms debounce
      } else if (nearTop) {
        // Log why we didn't trigger load more
        const reasons = [];
        if (isLoadingMore) reasons.push('already loading');
        if (!hasMoreMessages) reasons.push('no more messages');
        
        console.log('🔍 SCROLL DEBUG - Near top but not loading more:', reasons.join(', '));
      }
    } else {
      setShowScrollDownButton(false);
      setIsNearTop(false);
    }
  }, [isLoadingMore, hasMoreMessages, loadMoreMessages, messages.length]);

  // Add/remove scroll listener
  useEffect(() => {
    const container = scrollContainerRef.current;
    if (container) {
      container.addEventListener('scroll', handleScroll);
      // Initial check in case it loads scrolled up
      handleScroll(); 
      return () => {
        container.removeEventListener('scroll', handleScroll);
        // Clean up any pending debounced load attempts
        if (loadMoreDebounceRef.current) {
          clearTimeout(loadMoreDebounceRef.current);
        }
      };
    }
  }, [handleScroll]);
  
  // Cleanup debounce on unmount
  useEffect(() => {
    return () => {
      if (loadMoreDebounceRef.current) {
        clearTimeout(loadMoreDebounceRef.current);
      }
    };
  }, []);
  
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
  
  // IMPROVED: Function to get tool-specific icon with precise matching
  const getToolIcon = (toolName: string) => {
    // Normalize tool name for matching
    const normalizedTool = toolName?.toLowerCase() || '';
    
    console.log(`[getToolIcon] Mapping icon for tool: "${toolName}" (normalized: "${normalizedTool}")`);
    
    // === CHART TOOLS ===
    if (normalizedTool.includes('create_chart') || normalizedTool === 'create_chart') {
      return BarChartIcon;
    }
    if (normalizedTool.includes('create_chart_from_data')) {
      return PieChartIcon;
    }
    if (normalizedTool.includes('chart') && normalizedTool.includes('template')) {
      return DashboardIcon;
    }
    if (normalizedTool.includes('chart') || normalizedTool.includes('graph')) {
      return BarChartIcon;
    }
    
    // === DOCUMENT TOOLS ===
    if (normalizedTool === 'create_document' || normalizedTool.includes('create_document')) {
      return CreateIcon; // Pencil with plus sign - perfect for document creation
    }
    if (normalizedTool === 'edit_document' || normalizedTool.includes('edit_document')) {
      return EditIcon; // Standard edit pencil - for editing
    }
    if (normalizedTool.includes('append_content') || normalizedTool.includes('append')) {
      return PostAddIcon; // Document with plus - for appending content
    }
    if (normalizedTool.includes('create_document_with_chart')) {
      return ArticleIcon;
    }
    
    // === PREVIEW TOOLS ===
    if (normalizedTool === 'live_preview' || normalizedTool.includes('live_preview')) {
      return PlayArrowIcon; // Play button - perfect for starting live preview
    }
    if (normalizedTool.includes('preview') && !normalizedTool.includes('live')) {
      return VisibilityIcon; // Eye icon - for viewing/preview
    }
    
    // === FILESYSTEM TOOLS ===
    if (normalizedTool.includes('filesystem_read_file') || normalizedTool === 'read_file') {
      return ReadMoreIcon; // Reading icon
    }
    if (normalizedTool.includes('filesystem_write_file') || normalizedTool === 'write_file') {
      return CreateIcon; // Writing icon
    }
    if (normalizedTool.includes('filesystem_move_file') || normalizedTool === 'move_file') {
      return DriveFileMoveIcon; // Perfect for moving files
    }
    if (normalizedTool.includes('filesystem_copy_file') || normalizedTool === 'copy_file') {
      return ContentCopyIcon; // Copy icon
    }
    if (normalizedTool.includes('filesystem_list_') || normalizedTool.includes('list_directory')) {
      return ListIcon; // List icon for directory listings
    }
    if (normalizedTool.includes('filesystem_search_files') || normalizedTool.includes('search_files')) {
      return FindInPageIcon; // Search in files icon
    }
    if (normalizedTool.includes('filesystem_create_directory') || normalizedTool.includes('create_directory')) {
      return CreateNewFolderIcon; // Folder with plus
    }
    if (normalizedTool.includes('filesystem_get_info') || normalizedTool.includes('file_info')) {
      return InfoIcon; // Info icon
    }
    if (normalizedTool.includes('filesystem') && normalizedTool.includes('directory')) {
      return FolderOpenIcon; // Open folder icon
    }
    if (normalizedTool.includes('filesystem')) {
      return FileCopyIcon; // General file icon for other filesystem operations
    }
    
    // === SEARCH TOOLS ===
    if (normalizedTool.includes('websearch') || normalizedTool.includes('web_search')) {
      return TravelExploreIcon; // Globe with magnifying glass - perfect for web search
    }
    if (normalizedTool.includes('search') && !normalizedTool.includes('filesystem')) {
      return SearchIcon; // General search
    }
    
    // === WEB TOOLS ===
    if (normalizedTool.includes('fetch') || normalizedTool.includes('web_fetch')) {
      return PublicIcon; // Globe icon for web fetching
    }
    if (normalizedTool.includes('web') && !normalizedTool.includes('search')) {
      return WebIcon; // General web icon
    }
    
    // === CONVERSION TOOLS ===
    if (normalizedTool.includes('convert_to_md') || normalizedTool.includes('convert_from_md')) {
      return TransformIcon; // Transform/convert icon
    }
    if (normalizedTool.includes('convert') && normalizedTool.includes('pdf')) {
      return PictureAsPdfIcon; // PDF icon
    }
    if (normalizedTool.includes('convert')) {
      return CodeIcon; // Code/transform icon
    }
    
    // === IMAGE TOOLS ===
    if (normalizedTool.includes('add_image') || normalizedTool.includes('image')) {
      return ImageIcon;
    }
    
    // === MEMORY/STORAGE TOOLS ===
    if (normalizedTool.includes('qdrant') || normalizedTool.includes('store') || normalizedTool.includes('memory')) {
      return StorageIcon;
    }
    
    // === GENERIC DOCUMENT PATTERNS ===
    if (normalizedTool.includes('document') && !normalizedTool.includes('create') && !normalizedTool.includes('edit')) {
      return DescriptionIcon; // General document icon
    }
    
    // === FOLDER/DIRECTORY PATTERNS ===
    if (normalizedTool.includes('folder') || normalizedTool.includes('directory')) {
      return FolderIcon;
    }
    
    // === SETTINGS/CONFIG TOOLS ===
    if (normalizedTool.includes('config') || normalizedTool.includes('settings')) {
      return SettingsIcon;
    }
    
    // === DEFAULT FALLBACK ===
    console.log(`[getToolIcon] No specific match found for "${toolName}", using default FunctionsIcon`);
    return FunctionsIcon;
  };
  
  // Helper function to find tool result for a tool call
  const findToolResultForCall = (toolCallMessage: Message) => {
    const toolCallMessageIndex = messages.findIndex(msg => msg.id === toolCallMessage.id);
    
    if (toolCallMessageIndex === -1) {
      console.log(`[findToolResultForCall] Tool call message not found in messages array`);
      return null;
    }
    
    // Check if the next message is a tool result
    const nextMessage = messages[toolCallMessageIndex + 1];
    
    // Simple matching: if the next message is a tool result, it belongs to this tool call
    if (nextMessage && 
        (nextMessage.metadata?.stepType === 'Tool Result' || nextMessage.metadata?.isToolResult === true)) {
      console.log(`[findToolResultForCall] Found tool result immediately following tool call:`, {
        toolCallId: toolCallMessage.id,
        resultId: nextMessage.id,
        toolName: toolCallMessage.metadata?.toolName
      });
      return nextMessage;
    }
    
    console.log(`[findToolResultForCall] No tool result found immediately following tool call ${toolCallMessage.id}`);
    return null;
  };

  // Toggle tool call details
  const toggleToolCallDetails = (messageId: string) => {
    setExpandedToolCalls(prev => {
      const newSet = new Set(prev);
      if (newSet.has(messageId)) {
        newSet.delete(messageId);
      } else {
        newSet.add(messageId);
      }
      return newSet;
    });
  };

  // Render a single message
  const renderMessage = (message: Message, index: number) => {
    const isUserMessage = message.role === 'user';
    const isAssistantMessage = message.role === 'assistant';
    const isSystemMessage = message.role === 'system';
    
    // Check if this is an active tool call (currently running) vs completed (historical)
    // NEW: Also check for isToolCall flag set in real-time updates
    const isToolCall = message.metadata?.stepType === 'Calling Tool' || message.metadata?.isToolCall === true;
    const isToolResult = message.metadata?.stepType === 'Tool Result' || message.metadata?.isToolResult === true;
    const isLastMessage = index === messages.length - 1;
    
    // IMPROVED: Better active tool call detection
    // A tool call is "active" if:
    // 1. It's a tool call message AND
    // 2. No corresponding tool result exists yet AND
    // 3. It's the very last message in the conversation AND
    // 4. We're not currently loading more historical messages (no animation for historical tool calls)
    const hasToolResult = isToolCall ? findToolResultForCall(message) !== null : false;
    const isActiveToolCall = isToolCall && !hasToolResult && isLastMessage && !isLoadingMore;
    
    // Enhanced logging for animation debugging
    if (isToolCall) {
      console.log(`[Animation Debug] Tool: ${message.metadata?.toolName}, Index: ${index}/${messages.length}, IsLast: ${isLastMessage}, HasResult: ${hasToolResult}, IsActive: ${isActiveToolCall}, IsLoading: ${isLoading}, IsLoadingMore: ${isLoadingMore}`);
    }
    
    // Hide tool result messages - they'll be shown as part of tool call toggles
    if (isToolResult) {
      return null;
    }
    
    // For tool calls, use special rendering without bubble background
    const shouldUseFlatRendering = isToolCall;
    
    // --- ADDED LOG --- 
    console.log(`[ChatAreaNew - renderMessage] Rendering message ID: ${message.id}, Role: ${message.role}, StepType: ${message.metadata?.stepType}, isToolCall flag: ${message.metadata?.isToolCall}, Combined ToolCall: ${isToolCall}, isToolResult: ${isToolResult}, Active: ${isActiveToolCall}, ToolName: ${message.metadata?.toolName}, Files:`, message.files);
    // --- END ADDED LOG ---
    
    // Determine background color based on message role
    let bgColor;
    if (isUserMessage) {
      bgColor = theme.palette.mode === 'dark'
        ? alpha(theme.palette.primary.dark, 0.15)
        : alpha(theme.palette.primary.light, 0.15);
    } else if (isAssistantMessage) {
      // Use blue color for assistant messages instead of secondary (which was reddish)
      bgColor = theme.palette.mode === 'dark'
        ? alpha('#1976d2', 0.15) // Dark blue
        : alpha('#2196f3', 0.15); // Light blue
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
    
    // Special flat rendering for tool calls
    if (shouldUseFlatRendering) {
      return (
        <Box
          key={message.id || index}
          sx={{
            width: '100%',
            marginBottom: 1, // Reduced margin for tighter appearance
            paddingLeft: 2, // Small left padding for visual alignment
          }}
        >
          {hasAttachments && renderAttachments(attachmentsToRender)}
          
          {/* Render tool call content directly without bubble */}
          {isToolCall ? (
            <Box>
              {/* User-friendly tool call message - clickable to toggle details */}
              <Box
                onClick={() => toggleToolCallDetails(message.id)}
                sx={{
                  cursor: 'pointer',
                  padding: theme.spacing(1.5),
                  borderRadius: theme.spacing(1),
                  backgroundColor: 'transparent',
                  border: `1px solid ${theme.palette.mode === 'dark' 
                    ? alpha(theme.palette.grey[600], 0.3) 
                    : alpha(theme.palette.grey[400], 0.3)}`,
                  color: theme.palette.text.primary,
                  fontWeight: 500,
                  fontSize: '0.875rem',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 1.5,
                  transition: 'all 0.2s ease-in-out',
                  // Enhanced animation for active tool calls with timeout - SHIMMER ONLY
                  ...(isActiveToolCall ? {
                    // Only shimmer effect - no pulse or scale
                    position: 'relative',
                    overflow: 'hidden',
                    '&::before': {
                      content: '""',
                      position: 'absolute',
                      top: 0,
                      left: '-100%',
                      width: '100%',
                      height: '100%',
                      background: `linear-gradient(90deg, transparent, ${alpha(theme.palette.primary.main, 0.2)}, transparent)`,
                      animation: 'toolCallShimmer 3s ease-in-out infinite', // Changed to infinite instead of timed
                    },
                  } : {}),
                  '&:hover': {
                    backgroundColor: theme.palette.mode === 'dark' 
                      ? alpha(theme.palette.grey[700], 0.3)
                      : alpha(theme.palette.grey[300], 0.3),
                    borderColor: theme.palette.primary.main,
                  },
                }}
              >
                {/* Tool Icon */}
                {(() => {
                  const ToolIcon = getToolIcon(message.metadata?.toolName || '');
                  return (
                    <ToolIcon 
                      sx={{ 
                        fontSize: '1.25rem', // Consistent icon size
                        color: isActiveToolCall ? theme.palette.primary.main : theme.palette.text.secondary,
                        transition: 'color 0.2s ease-in-out',
                        // Removed icon pulse animation - just color change
                      }} 
                    />
                  );
                })()}
                
                <Typography variant="body2" component="span" sx={{ flexGrow: 1, zIndex: 1 }}>
                  {message.content || 
                    (message.metadata?.toolName ? `Calling ${message.metadata.toolName}...` : 'Calling tool...')
                  }
                </Typography>
                
                <Typography variant="caption" color="text.secondary" sx={{ zIndex: 1 }}>
                  {expandedToolCalls.has(message.id) ? '▼' : '▶'}
                </Typography>
              </Box>

              {/* Expandable tool details */}
              {expandedToolCalls.has(message.id) && (
                <Box
                  sx={{
                    mt: 1,
                    p: 2,
                    backgroundColor: theme.palette.mode === 'dark' 
                      ? alpha(theme.palette.grey[800], 0.5)
                      : alpha(theme.palette.grey[100], 0.8),
                    borderRadius: theme.spacing(1),
                    border: `1px solid ${theme.palette.mode === 'dark' 
                      ? alpha(theme.palette.grey[600], 0.3) 
                      : alpha(theme.palette.grey[400], 0.3)}`,
                  }}
                >
                  {/* Tool Parameters */}
                  {message.metadata?.toolArguments && (
                    <Box sx={{ mb: 2 }}>
                      <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 600, color: 'text.primary' }}>
                        Parameters:
                      </Typography>
                      <Box
                        component="div"
                        sx={{
                          backgroundColor: theme.palette.mode === 'dark' 
                            ? alpha(theme.palette.grey[900], 0.8)
                            : alpha(theme.palette.grey[50], 0.9),
                          padding: theme.spacing(1.5),
                          borderRadius: theme.spacing(1),
                          fontSize: '0.8rem',
                          fontFamily: 'monospace',
                          overflow: 'auto',
                          maxHeight: '300px',
                          border: `1px solid ${theme.palette.mode === 'dark' 
                            ? alpha(theme.palette.grey[600], 0.3) 
                            : alpha(theme.palette.grey[400], 0.3)}`,
                          '& pre': {
                            margin: 0,
                            fontFamily: 'inherit',
                            fontSize: 'inherit',
                            whiteSpace: 'pre-wrap',
                            wordBreak: 'break-word',
                          },
                          '& code': {
                            backgroundColor: 'transparent',
                            padding: 0,
                            borderRadius: 0,
                            fontSize: 'inherit',
                            fontFamily: 'inherit',
                          },
                        }}
                        dangerouslySetInnerHTML={{
                          __html: marked('```json\n' + (typeof message.metadata.toolArguments === 'string' 
                            ? message.metadata.toolArguments 
                            : JSON.stringify(message.metadata.toolArguments, null, 2)) + '\n```', { renderer })
                        }}
                      />
                    </Box>
                  )}

                  {/* Tool Result */}
                  {(() => {
                    const toolResult = findToolResultForCall(message);
                    console.log(`[Tool Result UI] Tool call ${message.id} (${message.metadata?.toolName}) - Found result:`, !!toolResult?.metadata?.toolResult);
                    
                    if (toolResult?.metadata?.toolResult) {
                      console.log(`[Tool Result UI] Displaying result for ${message.metadata?.toolName}:`, toolResult.metadata.toolResult.substring(0, 100) + '...');
                      return (
                        <Box>
                          <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 600, color: 'text.primary' }}>
                            ✓ Result:
                          </Typography>
                          <Box
                            component="div"
                            sx={{
                              backgroundColor: theme.palette.mode === 'dark' 
                                ? alpha(theme.palette.grey[900], 0.8)
                                : alpha(theme.palette.grey[50], 0.9),
                              padding: theme.spacing(1.5),
                              borderRadius: theme.spacing(1),
                              fontSize: '0.8rem',
                              overflow: 'auto',
                              maxHeight: '400px',
                              border: `1px solid ${theme.palette.mode === 'dark' 
                                ? alpha(theme.palette.grey[600], 0.3) 
                                : alpha(theme.palette.grey[400], 0.3)}`,
                              '& pre': {
                                margin: 0,
                                fontFamily: 'monospace',
                                fontSize: 'inherit',
                                whiteSpace: 'pre-wrap',
                                wordBreak: 'break-word',
                                backgroundColor: 'transparent',
                              },
                              '& code': {
                                backgroundColor: theme.palette.mode === 'dark' 
                                  ? alpha(theme.palette.grey[800], 0.6)
                                  : alpha(theme.palette.grey[200], 0.6),
                                padding: '0.1em 0.3em',
                                borderRadius: '3px',
                                fontSize: '0.9em',
                                fontFamily: 'monospace',
                              },
                              '& p': {
                                marginTop: '0.5em',
                                marginBottom: '0.5em',
                                '&:first-of-type': { marginTop: 0 },
                                '&:last-of-type': { marginBottom: 0 },
                              },
                              '& ul, & ol': {
                                marginTop: '0.5em',
                                marginBottom: '0.5em',
                                paddingLeft: '1.5em',
                              },
                              '& li': {
                                marginTop: '0.2em',
                                marginBottom: '0.2em',
                              },
                            }}
                            dangerouslySetInnerHTML={{
                              __html: marked(toolResult.metadata.toolResult, { renderer })
                            }}
                          />
                        </Box>
                      );
                    } else if (isActiveToolCall) {
                      return (
                        <Box>
                          <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 600, color: 'text.primary' }}>
                            ⋯ Result:
                          </Typography>
                          <Typography 
                            variant="body2" 
                            color="text.secondary" 
                            sx={{ 
                              fontStyle: 'italic',
                              // Simple opacity animation instead of pulse
                              animation: 'waitingFade 2s ease-in-out infinite',
                              '@keyframes waitingFade': {
                                '0%': { opacity: 0.4 },
                                '50%': { opacity: 1 },
                                '100%': { opacity: 0.4 },
                              },
                            }}
                          >
                            Waiting for result...
                          </Typography>
                        </Box>
                      );
                    } else {
                      console.log(`[Tool Result UI] No result found for tool call ${message.id} (${message.metadata?.toolName})`);
                      return null;
                    }
                  })()}
                </Box>
              )}
            </Box>
          ) : null}
          
          {/* Add filesystem activity display for assistant messages */}
          {isAssistantMessage && (
            <ChatFileSystemActivity messageId={message.id} />
          )}
        </Box>
      );
    }

    // Regular bubble rendering for non-tool messages
    return (
      <Box
        key={message.id || index}
        sx={{
          width: '100%',
          display: 'flex',
          justifyContent: isUserMessage ? 'flex-end' : 'flex-start',
          marginBottom: 1, // Reduced margin between messages
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
                : (message.metadata?.agentName || message.metadata?.agent || 'Assistant') // Use stored friendly name with fallbacks
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
          
          {/* Render content for non-tool messages */}
            <Box
              component="div" // Use a div to render HTML
              sx={{
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
                lineHeight: '1.4 !important', // Improved line height for readability
                fontFamily: 'inherit', // Use default font
                ...(theme.typography.body2),
              '& p': {
                marginTop: '0.1em', // Much smaller paragraph margins
                marginBottom: '0.1em',
              },
              '& h1, & h2, & h3, & h4, & h5, & h6': {
                marginTop: '0.3em', // Slightly larger for headings but still compact
                marginBottom: '0.1em',
              },
              '& ul, & ol': {
                marginTop: '0.1em', // Minimal list margins
                marginBottom: '0.1em',
                paddingLeft: '1.5em', // Reduced list indentation
              },
              '& li': {
                marginTop: '0.05em', // Very small list item margins
                marginBottom: '0.05em',
                lineHeight: '1.3', // Compact line height for list items
              },
              '& h1': { fontSize: '1.4em', fontWeight: 600 }, // Smaller heading sizes
              '& h2': { fontSize: '1.25em', fontWeight: 600 },
              '& h3': { fontSize: '1.1em', fontWeight: 600 },
              '& h4, & h5, & h6': { fontSize: '1em', fontWeight: 600 }, // Keep smaller headings closer to base size
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
                marginTop: '0.2em',
                marginBottom: '0.2em',
              }
            }}
            dangerouslySetInnerHTML={{
              __html: message.content ? marked(message.content, { renderer }) : '<i style="color: grey;">No content</i>' // Use the custom renderer
            }}
          />
          
          {/* Add streaming indicator for streaming messages with timeout */}
          {message.metadata?.isStreaming && (
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                mt: 1,
                opacity: 0.7,
                animation: 'fadeInOut 15s ease-in-out forwards', // 15 second timeout
                '@keyframes fadeInOut': {
                  '0%': { opacity: 0.7 },
                  '80%': { opacity: 0.7 }, // Keep visible for 12 seconds
                  '100%': { opacity: 0 }, // Fade out in last 3 seconds
                },
              }}
            >
              <Box
                sx={{
                  width: 8,
                  height: 8,
                  backgroundColor: theme.palette.primary.main,
                  borderRadius: '50%',
                  animation: 'pulse 1.5s ease-in-out infinite',
                  mr: 1,
                  '@keyframes pulse': {
                    '0%': {
                      opacity: 1,
                    },
                    '50%': {
                      opacity: 0.3,
                    },
                    '100%': {
                      opacity: 1,
                    },
                  },
                }}
              />
              <Typography
                variant="caption"
                color="text.secondary"
                sx={{ fontStyle: 'italic' }}
              >
                Streaming...
              </Typography>
            </Box>
          )}
          
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
          padding: 1, // Half of original padding: 2 -> 1 (16px -> 8px on all sides)
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
      
      {/* Image popup removed - now opens in external browser */}
    </Box>
  );
};

export default ChatAreaNew; 