import React, { useState, useCallback, useEffect, useRef, useMemo } from 'react';
import {
  Box,
  Drawer,
  Typography,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  ListItemButton,
  IconButton,
  Divider,
  TextField,
  useTheme,
  Tooltip,
  Menu,
  MenuItem,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  InputAdornment,
  Tabs,
  Tab,
  Badge,
  DialogContentText,
  Avatar,
  Checkbox,
  ButtonGroup,
  Fade,
  InputBase,
  Snackbar,
  Alert,
  CircularProgress
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import ChatIcon from '@mui/icons-material/Chat';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import DeleteIcon from '@mui/icons-material/Delete';
import DriveFileRenameOutlineIcon from '@mui/icons-material/DriveFileRenameOutline';
import CloseIcon from '@mui/icons-material/Close';
import SearchIcon from '@mui/icons-material/Search';
import SettingsIcon from '@mui/icons-material/Settings';
import FolderIcon from '@mui/icons-material/Folder';
import InsertDriveFileIcon from '@mui/icons-material/InsertDriveFile';
import DownloadIcon from '@mui/icons-material/Download';
import HelpIcon from '@mui/icons-material/Help';
import SortIcon from '@mui/icons-material/Sort';
import CheckBoxOutlineBlankIcon from '@mui/icons-material/CheckBoxOutlineBlank';
import CheckBoxIcon from '@mui/icons-material/CheckBox';
import ArrowUpwardIcon from '@mui/icons-material/ArrowUpward';
import ArrowDownwardIcon from '@mui/icons-material/ArrowDownward';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import CloudDoneIcon from '@mui/icons-material/CloudDone';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import { useNavigate } from 'react-router-dom';
import { format } from 'date-fns';

// Hooks
import { useMainWindowHooks } from '../../hooks';
import { useUser } from '../../hooks';

// Types
import { Conversation } from '../../types/conversation';

interface SideMenuProps {
  isOpen: boolean;
  isMobile: boolean;
  setIsOpen: (isOpen: boolean) => void;
  navbarHeight: number; // Add prop for navbar height
}

/**
 * SideMenu component for displaying and managing conversations and files
 */
const SideMenuNew: React.FC<SideMenuProps> = ({ isOpen, isMobile, setIsOpen, navbarHeight }) => {
  const theme = useTheme();
  const user = useUser();
  const navigate = useNavigate();
  const searchInputRef = useRef<HTMLInputElement>(null);
  
  // State for tabs
  const [activeTab, setActiveTab] = useState(0);
  
  // Search state
  const [isSearchVisible, setIsSearchVisible] = useState(false);
  
  // Selection state for conversations
  const [selectedConversations, setSelectedConversations] = useState<string[]>([]);
  const [selectionMode, setSelectionMode] = useState(false);
  
  // Sort order state
  const [sortOrder, setSortOrder] = useState<'newest' | 'oldest'>('newest');
  
  // Sort order state for files
  const [fileSortOrder, setFileSortOrder] = useState<'newest' | 'oldest'>('newest');
  
  // Initialize the menu anchor state
  const [menuAnchorEl, setMenuAnchorEl] = useState<null | HTMLElement>(null);
  const [selectedConversationId, setSelectedConversationId] = useState<string | null>(null);
  const [selectedFileId, setSelectedFileId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [isRenameDialogOpen, setIsRenameDialogOpen] = useState(false);
  const [newConversationTitle, setNewConversationTitle] = useState('');
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [isDeleteAllDialogOpen, setIsDeleteAllDialogOpen] = useState(false);
  const [isDeleteSelectedDialogOpen, setIsDeleteSelectedDialogOpen] = useState(false);
  
  // Toggle selection mode for files
  const [fileSelectionMode, setFileSelectionMode] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState<string[]>([]);
  
  // File search
  const [isFileSearchVisible, setIsFileSearchVisible] = useState(false);
  const [fileSearchQuery, setFileSearchQuery] = useState('');
  const [isDeleteSelectedFilesDialogOpen, setIsDeleteSelectedFilesDialogOpen] = useState(false);
  
  // Track if files have been loaded at least once to prevent unnecessary API calls
  const [filesLoadedOnce, setFilesLoadedOnce] = useState(false);
  
  // Track loading errors and retry attempts
  const [fileLoadError, setFileLoadError] = useState(false);
  const [fileLoadRetryCount, setFileLoadRetryCount] = useState(0);
  const MAX_RETRY_ATTEMPTS = 2; // Maximum number of retry attempts
  
  // Use ref to track the last load time to implement a debounce
  const lastFileLoadTimeRef = useRef<number>(0);
  const FILE_LOAD_DEBOUNCE_MS = 5000; // 5 seconds debounce
  
  // Track ids of recently uploaded files for highlighting
  const [recentlyUploadedFiles, setRecentlyUploadedFiles] = useState<string[]>([]);
  const [lastUploadTimestamp, setLastUploadTimestamp] = useState<number>(0);
  
  // File input ref for direct uploads
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  // File upload status
  const [uploadStatus, setUploadStatus] = useState<{
    isUploading: boolean;
    message: string;
    severity: 'success' | 'error' | 'info' | 'warning';
    autoHideDuration: number | null;
  }>({
    isUploading: false,
    message: '',
    severity: 'info',
    autoHideDuration: 3000
  });
  
  // Track existing file IDs before upload to identify new ones
  const [preUploadFileIds, setPreUploadFileIds] = useState<Set<string>>(new Set());
  
  // Store uploaded file IDs for highlighting
  const [uploadedFileIds, setUploadedFileIds] = useState<string[]>([]);
  
  // Get hooks from the main window hooks
  const { conversation, file, ui } = useMainWindowHooks();

  // Handle tab change
  const handleTabChange = (_: React.SyntheticEvent, newValue: number) => {
    setActiveTab(newValue);
    setSearchQuery('');
    setFileSearchQuery('');
    setSelectionMode(false);
    setFileSelectionMode(false);
    setSelectedConversations([]);
    setSelectedFiles([]);
    setIsSearchVisible(false);
    setIsFileSearchVisible(false); // Close search when changing tabs
    
    // If switching to files tab, check if we need to load files
    if (newValue === 1) {
      const now = Date.now();
      // Only trigger a load if we haven't loaded recently
      if (now - lastFileLoadTimeRef.current > FILE_LOAD_DEBOUNCE_MS) {
        checkAndLoadFiles();
      }
    }
  };
  
  // Close the drawer in mobile view
  const handleCloseDrawer = () => {
    if (isMobile) {
      setIsOpen(false);
    }
  };
  
  // Toggle search visibility
  const handleToggleSearch = () => {
    setIsSearchVisible(!isSearchVisible);
    // Focus the input when becoming visible
    if (!isSearchVisible) {
      setTimeout(() => {
        if (searchInputRef.current) {
          searchInputRef.current.focus();
        }
      }, 100);
    }
  };
  
  // Toggle sort order
  const handleToggleSortOrder = () => {
    setSortOrder(sortOrder === 'newest' ? 'oldest' : 'newest');
  };
  
  // Toggle selection mode
  const handleToggleSelectionMode = () => {
    setSelectionMode(!selectionMode);
    if (selectionMode) {
      setSelectedConversations([]);
    }
  };
  
  // Handle conversation selection
  const handleSelectConversationCheckbox = (convId: string) => {
    setSelectedConversations(prev => {
      if (prev.includes(convId)) {
        return prev.filter(id => id !== convId);
      } else {
        return [...prev, convId];
      }
    });
  };
  
  // Delete selected conversations
  const handleDeleteSelected = () => {
    if (selectedConversations.length > 0) {
      setIsDeleteSelectedDialogOpen(true);
    }
  };
  
  // Confirm deletion of selected conversations
  const handleDeleteSelectedConfirm = () => {
    try {
      for (const convId of selectedConversations) {
        conversation.deleteConversation(convId);
      }
    } catch (error) {
      console.error("Error deleting selected conversations:", error);
    } finally {
      setIsDeleteSelectedDialogOpen(false);
      setSelectedConversations([]);
      setSelectionMode(false);
    }
  };
  
  // Navigate to profile page
  const handleOpenProfilePage = () => {
    navigate('/profile');
    handleCloseDrawer();
  };

  // Navigate to settings page
  const handleOpenSettingsPage = () => {
    navigate('/settings');
    handleCloseDrawer();
  };

  // Navigate to feedback/help page
  const handleOpenFeedbackPage = () => {
    navigate('/feedback');
    handleCloseDrawer();
  };
  
  // Create a new conversation
  const handleCreateNewConversation = useCallback(async () => {
    try {
      const newId = await conversation.createConversation('New Conversation');
      conversation.setCurrentConversationId(newId);
      handleCloseDrawer();
    } catch (err) {
      console.error('Failed to create new conversation:', err);
    }
  }, [conversation, handleCloseDrawer]);
  
  // Select a conversation
  const handleSelectConversation = useCallback((convId: string) => {
    if (selectionMode) {
      handleSelectConversationCheckbox(convId);
    } else {
      conversation.setCurrentConversationId(convId);
      handleCloseDrawer();
    }
  }, [conversation, handleCloseDrawer, selectionMode]);
  
  // Handle direct right-click on conversation for future functionality
  // This will be used if we want to add right-click context menu later
  const handleConversationAction = (convId: string) => {
    if (selectionMode) {
      handleSelectConversationCheckbox(convId);
    } else {
      setSelectedConversationId(convId);
      // Could potentially open a right-click menu or handle other actions
    }
  };
  
  // Handle direct right-click on file for future functionality
  const handleFileAction = (fileId: string) => {
    if (fileSelectionMode) {
      handleSelectFileCheckbox(fileId);
    } else {
      file.toggleFileSelection(fileId);
    }
  };
  
  // Close the context menu
  const handleCloseMenu = () => {
    setMenuAnchorEl(null);
    setSelectedConversationId(null);
    setSelectedFileId(null);
  };
  
  // Open the rename dialog
  const handleRenameClick = () => {
    handleCloseMenu();
    if (selectedConversationId) {
      const conv = conversation.conversationList.find(c => c.id === selectedConversationId);
      if (conv) {
        setNewConversationTitle(conv.title);
        setIsRenameDialogOpen(true);
      }
    }
  };
  
  // Rename a conversation
  const handleRenameConfirm = async () => {
    if (selectedConversationId && newConversationTitle.trim()) {
      await conversation.updateTitle(selectedConversationId, newConversationTitle.trim());
      setIsRenameDialogOpen(false);
    }
  };
  
  // Open the delete dialog
  const handleDeleteClick = () => {
    handleCloseMenu();
    if (selectedConversationId || selectedFileId) {
      setIsDeleteDialogOpen(true);
    }
  };
  
  // Delete a conversation or file
  const handleDeleteConfirm = () => {
    console.log(`Deleting: conversationId=${selectedConversationId}, fileId=${selectedFileId}`);
    try {
      if (selectedConversationId) {
        conversation.deleteConversation(selectedConversationId);
        console.log(`Conversation deletion attempted for ID: ${selectedConversationId}`);
      } else if (selectedFileId) {
        file.deleteFile(selectedFileId);
        console.log(`File deletion attempted for ID: ${selectedFileId}`);
      }
    } catch (error) {
      console.error("Error during deletion:", error);
    } finally {
      setIsDeleteDialogOpen(false);
      setSelectedConversationId(null);
      setSelectedFileId(null);
    }
  };

  const handleDeleteAllConfirm = () => {
    console.log("Deleting all conversations");
    try {
      conversation.deleteAllConversations();
      console.log("All conversations deletion attempted");
    } catch (error) {
      console.error("Error during all conversations deletion:", error);
    } finally {
      setIsDeleteAllDialogOpen(false);
    }
  };

  // Handle file download
  const handleDownloadFile = () => {
    handleCloseMenu();
    if (selectedFileId) {
      const fileObj = file.files.find(f => f.id === selectedFileId);
      if (fileObj) {
        file.downloadFile(fileObj);
      }
    }
  };
  
  // Function to check and load files when needed
  const checkAndLoadFiles = useCallback(() => {
    // Skip if already loading
    if (file.isLoadingFiles) return;
    
    // Skip if we've tried too many times
    if (fileLoadRetryCount > MAX_RETRY_ATTEMPTS) return;
    
    // Skip if we recently loaded (debounce)
    const now = Date.now();
    if (now - lastFileLoadTimeRef.current < FILE_LOAD_DEBOUNCE_MS) return;
    
    // Load files if we haven't loaded them yet or if we have files (refresh is good)
    if (!filesLoadedOnce || (file.files && file.files.length > 0)) {
      lastFileLoadTimeRef.current = now;
      
      file.loadFiles().catch(() => {
        setFileLoadError(true);
        setFileLoadRetryCount(prev => prev + 1);
      });
      
      // Mark that we've attempted to load files
      setFilesLoadedOnce(true);
    }
  }, [file, filesLoadedOnce, fileLoadRetryCount]);
  
  // Handle manual refresh of files
  const handleRefreshFiles = () => {
    setFileLoadError(false);
    setFileLoadRetryCount(0);
    lastFileLoadTimeRef.current = Date.now();
    
    file.loadFiles().catch(() => {
      setFileLoadError(true);
    });
  };
  
  // Load files when tab is active
  useEffect(() => {
    if (activeTab === 1) {
      checkAndLoadFiles();
    }
  }, [activeTab, checkAndLoadFiles]);
  
  // Reset error state when successfully loading files
  useEffect(() => {
    if (!file.isLoadingFiles && !file.isError && file.files) {
      setFileLoadError(false);
      setFilesLoadedOnce(true);
    }
  }, [file.files, file.isLoadingFiles, file.isError]);
  
  // Format date for conversation list
  const formatConversationDate = (dateString: string): string => {
    const date = new Date(dateString);
    const today = new Date();
    const isToday = date.toDateString() === today.toDateString();
    
    if (isToday) {
      return `Today, ${format(date, 'HH:mm')}`;
    } else {
      return format(date, 'MMM d, HH:mm');
    }
  };
  
  // Filter conversations based on search query
  const filteredConversations = (conversation.conversationList || []).filter(conv => 
    conv.title.toLowerCase().includes(searchQuery.toLowerCase())
  ).sort((a, b) => {
    // Apply sort order
    const dateA = a.updatedAt ? new Date(a.updatedAt) : new Date(a.createdAt);
    const dateB = b.updatedAt ? new Date(b.updatedAt) : new Date(b.createdAt);
    
    return sortOrder === 'newest' 
      ? dateB.getTime() - dateA.getTime() // Newest first
      : dateA.getTime() - dateB.getTime(); // Oldest first
  });

  // Filter files based on search query and sort order
  const filteredFiles = useMemo(() => {
    let files = !fileSearchQuery.trim() 
      ? file.files.filter(f => !f.isDeleted)
      : file.files.filter(f => !f.isDeleted && f.filename.toLowerCase().includes(fileSearchQuery.toLowerCase().trim()));
    
    // Apply sort order
    return files.sort((a, b) => {
      const dateA = new Date(a.createdAt);
      const dateB = new Date(b.createdAt);
      
      return fileSortOrder === 'newest' 
        ? dateB.getTime() - dateA.getTime() // Newest first
        : dateA.getTime() - dateB.getTime(); // Oldest first
    });
  }, [file.files, fileSearchQuery, fileSortOrder]);
  
  // Set drawer width based on view mode
  const drawerWidth = isMobile ? '100%' : '50%';
  
  // Toggle selection mode for files
  const handleToggleFileSelectionMode = () => {
    setFileSelectionMode(!fileSelectionMode);
    if (fileSelectionMode) {
      setSelectedFiles([]);
    }
  };
  
  // Handle file selection
  const handleSelectFileCheckbox = (fileId: string) => {
    setSelectedFiles(prev => {
      if (prev.includes(fileId)) {
        return prev.filter(id => id !== fileId);
      } else {
        return [...prev, fileId];
      }
    });
  };
  
  // Delete selected files
  const handleDeleteSelectedFiles = () => {
    if (selectedFiles.length > 0) {
      setIsDeleteSelectedFilesDialogOpen(true);
    }
  };
  
  // Confirm deletion of selected files
  const handleDeleteSelectedFilesConfirm = async () => {
    try {
      for (const fileId of selectedFiles) {
        await file.deleteFile(fileId);
      }
    } catch (error) {
      console.error("Error deleting selected files:", error);
    } finally {
      setIsDeleteSelectedFilesDialogOpen(false);
      setSelectedFiles([]);
      setFileSelectionMode(false);
    }
  };
  
  // Download selected files
  const handleDownloadSelectedFiles = async () => {
    for (const fileId of selectedFiles) {
      try {
        await file.downloadFile(fileId);
      } catch (error) {
        console.error(`Error downloading file ${fileId}:`, error);
      }
    }
  };
  
  // Toggle file search visibility
  const handleToggleFileSearch = () => {
    setIsFileSearchVisible(!isFileSearchVisible);
    // Focus the input when becoming visible
    if (!isFileSearchVisible) {
      setTimeout(() => {
        if (searchInputRef.current) {
          searchInputRef.current.focus();
        }
      }, 100);
    }
  };
  
  // Toggle sort order for files
  const handleToggleFileSortOrder = () => {
    setFileSortOrder(fileSortOrder === 'newest' ? 'oldest' : 'newest');
  };
  
  // Close upload status notification
  const handleCloseUploadStatus = () => {
    setUploadStatus(prev => ({
      ...prev,
      message: ''
    }));
  };

  // Helper function to capture newly uploaded files
  const updateUploadedFileIds = (newFiles: string[]) => {
    setUploadedFileIds(newFiles);
    
    // Clear highlights after a delay
    setTimeout(() => {
      setUploadedFileIds([]);
    }, 5000); // Increased to 5 seconds for better visibility
  };

  // Monitor file upload progress
  useEffect(() => {
    if (file.isUploading) {
      setUploadStatus({
        isUploading: true,
        message: 'Uploading files...',
        severity: 'info',
        autoHideDuration: null // Don't auto-hide while uploading
      });
    } else if (!file.isUploading && uploadStatus.isUploading) {
      // Transition from uploading to not uploading
      if (file.error) {
        setUploadStatus({
          isUploading: false,
          message: `Upload failed: ${file.error}`,
          severity: 'error',
          autoHideDuration: 5000
        });
      } else {
        // Find newly added files by comparing with pre-upload file IDs
        const newlyAddedFiles = file.files
          .filter(f => !f.isDeleted && !preUploadFileIds.has(f.id))
          .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
          .slice(0, 5) // Limit to 5 most recent files
          .map(f => f.id);
        
        // Update highlighted files
        setRecentlyUploadedFiles(newlyAddedFiles);
        updateUploadedFileIds(newlyAddedFiles);
        
        // Clear the pre-upload IDs after successful upload
        setPreUploadFileIds(new Set());
        
        setUploadStatus({
          isUploading: false,
          message: `${newlyAddedFiles.length} file(s) uploaded successfully!`,
          severity: 'success',
          autoHideDuration: 3000
        });
      }
    }
  }, [file.isUploading, file.error, uploadStatus.isUploading, file.files, preUploadFileIds]);

  // Handle file uploads directly
  const handleDirectFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (!files || files.length === 0) return;
    
    // Clear any existing highlights when starting a new upload
    setUploadedFileIds([]);
    setRecentlyUploadedFiles([]);
    
    // Store current file IDs before upload
    const currentFileIds = new Set(file.files.map(f => f.id));
    setPreUploadFileIds(currentFileIds);
    
    // Convert FileList to array
    const fileArray = Array.from(files);
    
    // Show initial upload status
    setUploadStatus({
      isUploading: true,
      message: `Preparing to upload ${fileArray.length} file(s)...`,
      severity: 'info',
      autoHideDuration: null
    });
    
    // Validate and upload files
    const validFiles = file.validateFiles(fileArray);
    if (validFiles.length > 0) {
      file.uploadFiles(validFiles).catch(error => {
        console.error('Error uploading files:', error);
        setUploadStatus({
          isUploading: false,
          message: `Upload failed: ${error.message || 'Unknown error'}`,
          severity: 'error',
          autoHideDuration: 5000
        });
      });
    } else {
      // All files were invalid
      setUploadStatus({
        isUploading: false,
        message: 'No valid files to upload. Files may be too large or in an unsupported format.',
        severity: 'warning',
        autoHideDuration: 5000
      });
    }
    
    // Clear the input value so the same file can be selected again
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };
  
  // Trigger file input click
  const handleUploadButtonClick = () => {
    if (fileInputRef.current) {
      fileInputRef.current.click();
    }
  };
  
  // Handle double-click on file for downloading
  const handleFileDoubleClick = (fileId: string) => {
    if (!fileSelectionMode) {
      // Get the file object
      const fileObj = file.files.find(f => f.id === fileId);
      if (fileObj) {
        file.downloadFile(fileObj.id);
      }
    }
  };
  
  return (
    <>
      <Drawer
        variant={isMobile ? 'temporary' : 'persistent'}
        open={isOpen}
        onClose={handleCloseDrawer}
        sx={{
          width: drawerWidth,
          maxWidth: 320,
          flexShrink: 0,
          '& .MuiDrawer-paper': {
            width: drawerWidth,
            maxWidth: 320,
            boxSizing: 'border-box',
            backgroundColor: theme.palette.mode === 'dark' 
              ? 'rgba(0, 0, 0, 0.75)' 
              : 'rgba(255, 255, 255, 0.85)',
            backdropFilter: 'blur(10px)',
            borderRight: `1px solid ${theme.palette.divider}`,
            height: `calc(100% - ${navbarHeight}px)`,
            marginTop: `${navbarHeight}px`,
          },
        }}
      >
        <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
          {/* User Profile Section */}
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              p: 2,
              borderBottom: `1px solid ${theme.palette.divider}`,
            }}
          >
            <Avatar
              src={user.profile?.picture || ''}
              alt={user.profile?.name || 'User'}
              sx={{ 
                width: 48, 
                height: 48, 
                cursor: 'pointer',
                mr: 2,
                bgcolor: theme.palette.grey[700],
                '&:hover': {
                  opacity: 0.8,
                }
              }}
              onClick={handleOpenProfilePage}
            />
            <Box>
              <Typography variant="subtitle1" fontWeight="bold" noWrap>
                {user.profile?.name || 'User'}
              </Typography>
              <Typography variant="body2" color="text.secondary" noWrap>
                {user.profile?.email || ''}
              </Typography>
            </Box>

            {isMobile && (
              <IconButton 
                onClick={handleCloseDrawer}
                sx={{ ml: 'auto' }}
              >
                <CloseIcon />
              </IconButton>
            )}
          </Box>
          
          {/* Tabs */}
          <Tabs 
            value={activeTab} 
            onChange={handleTabChange}
            variant="fullWidth"
            sx={{ borderBottom: 1, borderColor: 'divider' }}
          >
            <Tab 
              label={
                <Badge 
                  badgeContent={conversation.conversationList.length} 
                  color="primary"
                  max={99}
                  sx={{ 
                    '& .MuiBadge-badge': { 
                      right: -12, 
                      top: -3,
                      fontSize: '0.65rem',
                      height: 16,
                      minWidth: 16,
                      padding: '0 4px'
                    } 
                  }}
                >
                  <Box sx={{ display: 'flex', alignItems: 'center' }}>
                    <ChatIcon fontSize="small" sx={{ mr: 0.5 }} />
                    <Typography variant="body2">Chats</Typography>
                  </Box>
                </Badge>
              } 
            />
            <Tab 
              label={
                <Badge 
                  badgeContent={file.files.length} 
                  color="primary"
                  max={99}
                  sx={{ 
                    '& .MuiBadge-badge': { 
                      right: -12, 
                      top: -3,
                      fontSize: '0.65rem',
                      height: 16,
                      minWidth: 16,
                      padding: '0 4px'
                    } 
                  }}
                >
                  <Box sx={{ display: 'flex', alignItems: 'center' }}>
                    <FolderIcon fontSize="small" sx={{ mr: 0.5 }} />
                    <Typography variant="body2">Files</Typography>
                    {file.isUploading && (
                      <CircularProgress 
                        size={10} 
                        thickness={10} 
                        sx={{ ml: 0.5 }} 
                      />
                    )}
                  </Box>
                </Badge>
              }
            />
          </Tabs>
          
          {/* Action buttons for conversations tab */}
          {activeTab === 0 && (
            <Box 
              sx={{ 
                px: 2, 
                py: 1, 
                display: 'flex', 
                justifyContent: 'space-between',
                alignItems: 'center',
                borderBottom: `1px solid ${theme.palette.divider}`,
              }}
            >
              <Box sx={{ display: 'flex', gap: 0.5 }}>
                <Tooltip title="New Conversation">
                  <IconButton
                    onClick={handleCreateNewConversation}
                    size="small"
                    sx={{ 
                      padding: 0.75,
                      color: theme.palette.text.secondary,
                      '&:hover': { 
                        color: theme.palette.primary.main,
                        backgroundColor: theme.palette.action.hover
                      },
                      '&:active': {
                        color: theme.palette.primary.dark
                      }
                    }}
                  >
                    <AddIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
                
                <Tooltip title={sortOrder === 'newest' ? 'Sort by Oldest' : 'Sort by Newest'}>
                  <IconButton
                    onClick={handleToggleSortOrder}
                    size="small"
                    sx={{ 
                      padding: 0.75,
                      color: theme.palette.text.secondary,
                      '&:hover': { 
                        color: theme.palette.primary.main,
                        backgroundColor: theme.palette.action.hover
                      },
                      '&:active': {
                        color: theme.palette.primary.dark
                      }
                    }}
                  >
                    {sortOrder === 'newest' ? <ArrowDownwardIcon fontSize="small" /> : <ArrowUpwardIcon fontSize="small" />}
                  </IconButton>
                </Tooltip>
                
                <Tooltip title={selectionMode ? 'Cancel Selection' : 'Select Conversations'}>
                  <IconButton
                    onClick={handleToggleSelectionMode}
                    size="small"
                    sx={{ 
                      padding: 0.75,
                      color: selectionMode ? theme.palette.primary.main : theme.palette.text.secondary,
                      backgroundColor: selectionMode ? theme.palette.action.selected : 'transparent',
                      '&:hover': { 
                        color: theme.palette.primary.main,
                        backgroundColor: selectionMode 
                          ? theme.palette.action.selected 
                          : theme.palette.action.hover
                      },
                      '&:active': {
                        color: theme.palette.primary.dark
                      }
                    }}
                  >
                    {selectionMode 
                      ? <CheckBoxIcon fontSize="small" /> 
                      : <CheckBoxOutlineBlankIcon fontSize="small" />
                    }
                  </IconButton>
                </Tooltip>
                
                <Tooltip title="Search Conversations">
                  <IconButton
                    onClick={handleToggleSearch}
                    size="small"
                    sx={{ 
                      padding: 0.75,
                      color: isSearchVisible ? theme.palette.primary.main : theme.palette.text.secondary,
                      backgroundColor: isSearchVisible ? theme.palette.action.selected : 'transparent',
                      '&:hover': { 
                        color: theme.palette.primary.main,
                        backgroundColor: isSearchVisible 
                          ? theme.palette.action.selected 
                          : theme.palette.action.hover
                      },
                      '&:active': {
                        color: theme.palette.primary.dark
                      }
                    }}
                  >
                    <SearchIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
              </Box>
              
              <Box sx={{ display: 'flex', alignItems: 'center' }}>
                {/* Search input - only visible when search is toggled */}
                {isSearchVisible && (
                  <Fade in={isSearchVisible}>
                    <InputBase
                      inputRef={searchInputRef}
                      placeholder="Search..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      sx={{ 
                        fontSize: '0.875rem',
                        ml: 1,
                        color: theme.palette.text.primary,
                        '& .MuiInputBase-input': {
                          padding: '4px 8px',
                          borderRadius: 1,
                          backgroundColor: 'rgba(0, 0, 0, 0.05)',
                          '&:focus': {
                            backgroundColor: 'rgba(0, 0, 0, 0.09)'
                          }
                        }
                      }}
                      onKeyDown={(e) => {
                        if (e.key === 'Escape') {
                          setIsSearchVisible(false);
                          setSearchQuery('');
                        }
                      }}
                    />
                  </Fade>
                )}
                
                {selectionMode && (
                  <Tooltip title="Delete Selected">
                    <IconButton
                      onClick={handleDeleteSelected}
                      size="small"
                      disabled={selectedConversations.length === 0}
                      sx={{ 
                        padding: 0.75,
                        color: selectedConversations.length === 0 
                          ? theme.palette.text.disabled 
                          : theme.palette.error.main,
                        '&:hover': selectedConversations.length > 0 ? { 
                          color: theme.palette.error.dark,
                          backgroundColor: theme.palette.action.hover
                        } : {},
                        '&:active': selectedConversations.length > 0 ? {
                          color: theme.palette.error.dark
                        } : {}
                      }}
                    >
                      <DeleteIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                )}
              </Box>
            </Box>
          )}
          
          {/* Content area - Either conversations or files */}
          <Box sx={{ flexGrow: 1, overflow: 'auto' }}>
            {activeTab === 0 ? (
              /* Conversations Tab */
              <List>
                {filteredConversations.map((conv) => (
                  <ListItem 
                    key={conv.id} 
                    disablePadding
                    secondaryAction={
                      selectionMode ? (
                        <Checkbox
                          edge="end"
                          checked={selectedConversations.includes(conv.id)}
                          onChange={() => handleSelectConversationCheckbox(conv.id)}
                          inputProps={{ 'aria-labelledby': `checkbox-list-label-${conv.id}` }}
                        />
                      ) : null
                    }
                  >
                    <ListItemButton
                      selected={!selectionMode && conv.id === conversation.currentConversationId}
                      onClick={() => handleSelectConversation(conv.id)}
                      sx={{
                        borderRadius: 1,
                        mx: 1,
                        my: 0.5,
                        '&.Mui-selected': {
                          backgroundColor: theme.palette.mode === 'dark' 
                            ? 'rgba(144, 202, 249, 0.16)' 
                            : 'rgba(25, 118, 210, 0.08)',
                        },
                      }}
                    >
                      <ListItemIcon sx={{ minWidth: 36 }}>
                        <ChatIcon fontSize="small" />
                      </ListItemIcon>
                      <ListItemText 
                        primary={conv.title} 
                        secondary={formatConversationDate(conv.updatedAt || conv.createdAt)}
                        primaryTypographyProps={{ 
                          noWrap: true,
                          style: { 
                            maxWidth: '150px',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis'
                          }
                        }}
                      />
                    </ListItemButton>
                  </ListItem>
                ))}
              </List>
            ) : (
              /* Files Tab */
              <>
                {/* File toolbar - similar to conversation toolbar but for files */}
                <Box sx={{ 
                  display: 'flex', 
                  justifyContent: 'space-between', 
                  alignItems: 'center',
                  pt: 1,
                  pb: 1,
                  px: 2,
                  borderBottom: `1px solid ${theme.palette.divider}`
                }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                    <Tooltip title={file.isUploading ? "Uploading..." : "Upload Files"}>
                      <IconButton
                        onClick={handleUploadButtonClick}
                        size="small"
                        sx={{ 
                          padding: 0.75,
                          color: file.isUploading ? theme.palette.primary.main : theme.palette.text.secondary,
                          position: 'relative',
                          '&:hover': { 
                            color: theme.palette.primary.main,
                            backgroundColor: theme.palette.action.hover
                          },
                          '&:active': {
                            color: theme.palette.primary.dark
                          }
                        }}
                      >
                        <AddIcon fontSize="small" />
                        {file.isUploading && (
                          <CircularProgress 
                            size={24} 
                            thickness={4} 
                            sx={{ 
                              position: 'absolute',
                              top: '50%',
                              left: '50%',
                              marginTop: '-12px',
                              marginLeft: '-12px',
                              color: theme.palette.primary.main
                            }} 
                          />
                        )}
                      </IconButton>
                    </Tooltip>
                    
                    <Tooltip title={fileSortOrder === 'newest' ? 'Sort by Oldest' : 'Sort by Newest'}>
                      <IconButton
                        onClick={handleToggleFileSortOrder}
                        size="small"
                        sx={{ 
                          padding: 0.75,
                          color: theme.palette.text.secondary,
                          '&:hover': { 
                            color: theme.palette.primary.main,
                            backgroundColor: theme.palette.action.hover
                          },
                          '&:active': {
                            color: theme.palette.primary.dark
                          }
                        }}
                      >
                        {fileSortOrder === 'newest' ? <ArrowDownwardIcon fontSize="small" /> : <ArrowUpwardIcon fontSize="small" />}
                      </IconButton>
                    </Tooltip>
                    
                    <Tooltip title={fileSelectionMode ? 'Cancel Selection' : 'Select Files'}>
                      <IconButton
                        onClick={handleToggleFileSelectionMode}
                        size="small"
                        sx={{ 
                          padding: 0.75,
                          color: fileSelectionMode ? theme.palette.primary.main : theme.palette.text.secondary,
                          backgroundColor: fileSelectionMode ? theme.palette.action.selected : 'transparent',
                          '&:hover': { 
                            color: theme.palette.primary.main,
                            backgroundColor: fileSelectionMode 
                              ? theme.palette.action.selected 
                              : theme.palette.action.hover
                          },
                          '&:active': {
                            color: theme.palette.primary.dark
                          }
                        }}
                      >
                        {fileSelectionMode 
                          ? <CheckBoxIcon fontSize="small" /> 
                          : <CheckBoxOutlineBlankIcon fontSize="small" />
                        }
                      </IconButton>
                    </Tooltip>
                    
                    <Tooltip title="Search Files">
                      <IconButton
                        onClick={handleToggleFileSearch}
                        size="small"
                        sx={{ 
                          padding: 0.75,
                          color: isFileSearchVisible ? theme.palette.primary.main : theme.palette.text.secondary,
                          backgroundColor: isFileSearchVisible ? theme.palette.action.selected : 'transparent',
                          '&:hover': { 
                            color: theme.palette.primary.main,
                            backgroundColor: isFileSearchVisible 
                              ? theme.palette.action.selected 
                              : theme.palette.action.hover
                          },
                          '&:active': {
                            color: theme.palette.primary.dark
                          }
                        }}
                      >
                        <SearchIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  </Box>
                  
                  <Box sx={{ display: 'flex', alignItems: 'center' }}>
                    {/* Search input - only visible when search is toggled */}
                    {isFileSearchVisible && (
                      <Fade in={isFileSearchVisible}>
                        <InputBase
                          inputRef={searchInputRef}
                          placeholder="Search files..."
                          value={fileSearchQuery}
                          onChange={(e) => setFileSearchQuery(e.target.value)}
                          sx={{ 
                            fontSize: '0.875rem',
                            ml: 1,
                            color: theme.palette.text.primary,
                            '& .MuiInputBase-input': {
                              padding: '4px 8px',
                              borderRadius: 1,
                              backgroundColor: 'rgba(0, 0, 0, 0.05)',
                              '&:focus': {
                                backgroundColor: 'rgba(0, 0, 0, 0.09)'
                              }
                            }
                          }}
                          onKeyDown={(e) => {
                            if (e.key === 'Escape') {
                              setIsFileSearchVisible(false);
                              setFileSearchQuery('');
                            }
                          }}
                        />
                      </Fade>
                    )}
                    
                    {fileSelectionMode && (
                      <Tooltip title="Delete Selected">
                        <IconButton
                          onClick={handleDeleteSelectedFiles}
                          size="small"
                          disabled={selectedFiles.length === 0}
                          sx={{ 
                            padding: 0.75,
                            color: selectedFiles.length === 0 
                              ? theme.palette.text.disabled 
                              : theme.palette.error.main,
                            '&:hover': selectedFiles.length > 0 ? { 
                              color: theme.palette.error.dark,
                              backgroundColor: theme.palette.action.hover
                            } : {},
                            '&:active': selectedFiles.length > 0 ? {
                              color: theme.palette.error.dark
                            } : {}
                          }}
                        >
                          <DeleteIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    )}
                  </Box>
                </Box>
                
                <List>
                  {file.isLoadingFiles ? (
                    <ListItem>
                      <ListItemText primary="Loading files..." />
                    </ListItem>
                  ) : fileLoadError ? (
                    <ListItem>
                      <Box sx={{ textAlign: 'center', width: '100%' }}>
                        <ListItemText 
                          primary="Failed to load files" 
                          secondary="There was an error loading your files"
                        />
                        <Button 
                          size="small" 
                          onClick={handleRefreshFiles}
                          sx={{ 
                            mt: 1,
                            color: theme.palette.primary.main,
                            '&:hover': {
                              backgroundColor: 'rgba(0, 0, 0, 0.04)'
                            }
                          }}
                        >
                          Retry
                        </Button>
                      </Box>
                    </ListItem>
                  ) : filteredFiles.length === 0 ? (
                    <ListItem>
                      <ListItemText primary="No files found" />
                    </ListItem>
                  ) : (
                    filteredFiles.map((fileItem) => (
                      <ListItem 
                        key={fileItem.id} 
                        disablePadding
                        secondaryAction={
                          fileSelectionMode ? (
                            <Checkbox
                              edge="end"
                              checked={selectedFiles.includes(fileItem.id)}
                              onChange={() => handleSelectFileCheckbox(fileItem.id)}
                              inputProps={{ 'aria-labelledby': `checkbox-file-list-label-${fileItem.id}` }}
                            />
                          ) : null
                        }
                      >
                        <ListItemButton
                          onClick={() => fileSelectionMode ? handleSelectFileCheckbox(fileItem.id) : file.toggleFileSelection(fileItem.id)}
                          onDoubleClick={() => handleFileDoubleClick(fileItem.id)}
                          selected={!fileSelectionMode && file.selectedFileIds.includes(fileItem.id)}
                          sx={{
                            borderRadius: 1,
                            mx: 1,
                            my: 0.5,
                            ...(uploadedFileIds.includes(fileItem.id) && {
                              backgroundColor: theme.palette.mode === 'dark' 
                                ? 'rgba(76, 175, 80, 0.25)' 
                                : 'rgba(76, 175, 80, 0.15)',
                              boxShadow: `0 0 8px ${theme.palette.success.main}`,
                              position: 'relative',
                              zIndex: 1,
                              '&::after': {
                                content: '""',
                                position: 'absolute',
                                top: 0,
                                left: 0,
                                right: 0,
                                bottom: 0,
                                borderRadius: 'inherit',
                                animation: 'highlight-pulse 1.5s ease-in-out infinite',
                                zIndex: -1
                              },
                              '@keyframes highlight-pulse': {
                                '0%': {
                                  boxShadow: `0 0 0 0 ${theme.palette.mode === 'dark' 
                                    ? 'rgba(76, 175, 80, 0.8)' 
                                    : 'rgba(76, 175, 80, 0.6)'}`,
                                  opacity: 1
                                },
                                '70%': {
                                  boxShadow: `0 0 0 10px ${theme.palette.mode === 'dark' 
                                    ? 'rgba(76, 175, 80, 0)' 
                                    : 'rgba(76, 175, 80, 0)'}`,
                                  opacity: 0.7
                                },
                                '100%': {
                                  boxShadow: `0 0 0 0 ${theme.palette.mode === 'dark' 
                                    ? 'rgba(76, 175, 80, 0)' 
                                    : 'rgba(76, 175, 80, 0)'}`,
                                  opacity: 1
                                }
                              }
                            })
                          }}
                        >
                          <ListItemIcon sx={{ minWidth: 36 }}>
                            <InsertDriveFileIcon fontSize="small" />
                          </ListItemIcon>
                          <ListItemText 
                            primary={fileItem.filename}
                            secondary={new Date(fileItem.createdAt).toLocaleDateString()}
                            primaryTypographyProps={{ 
                              noWrap: true,
                              style: { 
                                maxWidth: '150px',
                                overflow: 'hidden',
                                textOverflow: 'ellipsis'
                              }
                            }}
                          />
                        </ListItemButton>
                      </ListItem>
                    ))
                  )}
                </List>
              </>
            )}
          </Box>
          
          {/* Bottom toolbar */}
          <Box
            sx={{
              display: 'flex',
              justifyContent: 'space-between',
              p: 2,
              borderTop: `1px solid ${theme.palette.divider}`,
            }}
          >
            <Tooltip title="Settings">
              <IconButton onClick={handleOpenSettingsPage} sx={{
                color: theme.palette.text.secondary,
                '&:hover': { 
                  color: theme.palette.primary.main,
                  backgroundColor: theme.palette.action.hover
                }
              }}>
                <SettingsIcon />
              </IconButton>
            </Tooltip>
            
            <Tooltip title="Help & Feedback">
              <IconButton onClick={handleOpenFeedbackPage} sx={{
                color: theme.palette.text.secondary,
                '&:hover': { 
                  color: theme.palette.primary.main,
                  backgroundColor: theme.palette.action.hover
                }
              }}>
                <HelpIcon />
              </IconButton>
            </Tooltip>
          </Box>
        </Box>
      </Drawer>

      {/* Hidden file input for direct uploads */}
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleDirectFileUpload}
        style={{ display: 'none' }}
        multiple
        accept="image/*,application/pdf,text/*,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
      />

      {/* Context Menu - Keeping structure but not showing it since three-dot menus are removed */}
      <Menu
        anchorEl={menuAnchorEl}
        open={false} // Always closed since we removed the three-dot menu buttons
        onClose={handleCloseMenu}
      >
        {/* Menu content preserved but not used */}
      </Menu>

      {/* Upload Status Indicator */}
      <Snackbar
        open={!!uploadStatus.message}
        autoHideDuration={uploadStatus.autoHideDuration}
        onClose={handleCloseUploadStatus}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert 
          onClose={handleCloseUploadStatus} 
          severity={uploadStatus.severity}
          icon={
            uploadStatus.isUploading ? <CloudUploadIcon /> : 
            uploadStatus.severity === 'success' ? <CloudDoneIcon /> : 
            uploadStatus.severity === 'error' ? <ErrorOutlineIcon /> : undefined
          }
          sx={{
            display: 'flex',
            alignItems: 'center',
            '& .MuiAlert-icon': {
              display: 'flex',
              alignItems: 'center',
              pr: 0
            }
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center' }}>
            {uploadStatus.message}
            {uploadStatus.isUploading && (
              <CircularProgress 
                size={16} 
                thickness={5} 
                sx={{ ml: 1 }} 
              />
            )}
          </Box>
        </Alert>
      </Snackbar>

      {/* Rename Dialog */}
      <Dialog open={isRenameDialogOpen} onClose={() => setIsRenameDialogOpen(false)}>
        <DialogTitle>Rename Conversation</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            margin="dense"
            label="Conversation Name"
            type="text"
            fullWidth
            value={newConversationTitle}
            onChange={(e) => setNewConversationTitle(e.target.value)}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setIsRenameDialogOpen(false)}>Cancel</Button>
          <Button onClick={handleRenameConfirm}>Rename</Button>
        </DialogActions>
      </Dialog>

      {/* Delete Dialog */}
      <Dialog
        open={isDeleteDialogOpen}
        onClose={() => setIsDeleteDialogOpen(false)}
      >
        <DialogTitle>Confirm Deletion</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Are you sure you want to delete this {selectedConversationId ? 'conversation' : 'file'}?
            This action cannot be undone.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setIsDeleteDialogOpen(false)}>Cancel</Button>
          <Button onClick={handleDeleteConfirm} color="error" autoFocus>
            Delete
          </Button>
        </DialogActions>
      </Dialog>

      {/* Delete All Conversations Dialog */}
      <Dialog
        open={isDeleteAllDialogOpen}
        onClose={() => setIsDeleteAllDialogOpen(false)}
      >
        <DialogTitle>Confirm Delete All Conversations</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Are you sure you want to delete ALL conversations? This action cannot be undone.
            A new empty conversation will be created automatically.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setIsDeleteAllDialogOpen(false)}>Cancel</Button>
          <Button onClick={handleDeleteAllConfirm} color="error" autoFocus>
            Delete All
          </Button>
        </DialogActions>
      </Dialog>
      
      {/* Delete Selected Conversations Dialog */}
      <Dialog
        open={isDeleteSelectedDialogOpen}
        onClose={() => setIsDeleteSelectedDialogOpen(false)}
      >
        <DialogTitle>Confirm Deletion</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Are you sure you want to delete {selectedConversations.length} selected conversation{selectedConversations.length > 1 ? 's' : ''}?
            This action cannot be undone.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setIsDeleteSelectedDialogOpen(false)}>Cancel</Button>
          <Button onClick={handleDeleteSelectedConfirm} color="error" autoFocus>
            Delete Selected
          </Button>
        </DialogActions>
      </Dialog>

      {/* Delete Selected Files Dialog */}
      <Dialog
        open={isDeleteSelectedFilesDialogOpen}
        onClose={() => setIsDeleteSelectedFilesDialogOpen(false)}
      >
        <DialogTitle>Confirm Deletion</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Are you sure you want to delete {selectedFiles.length} selected file{selectedFiles.length > 1 ? 's' : ''}?
            This action cannot be undone.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setIsDeleteSelectedFilesDialogOpen(false)}>Cancel</Button>
          <Button onClick={handleDeleteSelectedFilesConfirm} color="error" autoFocus>
            Delete Selected
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
};

export default SideMenuNew; 