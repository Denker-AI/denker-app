import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { Box, useTheme, Snackbar, Alert, useMediaQuery, Button, AlertColor } from '@mui/material';
import ReplayIcon from '@mui/icons-material/Replay';
import { v4 as uuidv4 } from 'uuid';
import { getUserInfoCached } from '../utils/user-info-cache';
import { getCachedAccessToken } from '../utils/token-cache';

// Components
import NavBarNew from '../components/MainWindow/NavBarNew';
import ChatAreaNew from '../components/MainWindow/ChatAreaNew';
import InputBoxNew from '../components/MainWindow/InputBoxNew';
import SideMenuNew from '../components/MainWindow/SideMenuNew';
import AgentStatusIndicator from '../components/AgentStatusIndicator';

// Hooks
import { useMainWindowHooks } from '../hooks';
import { useAuth } from '../auth/AuthContext';
import { api } from '../services/api';
import { Message } from '../types/types';
import useMessageDatabaseUtils from '../hooks/conversation/messageDatabaseUtils';
import { FileAttachment } from '../hooks/conversation/types';
import useRealTimeUpdates from '../hooks/conversation/useRealTimeUpdates';

// Import MCPAgentClient with TypeScript support now available
import MCPAgentClient from '../utils/mcp-agent-client'; // Use import for ES modules

// --- TYPE DEFINITIONS (Local to this file for now) ---
interface ElectronAPI { // Local definition for this file
  getAccessToken?: () => Promise<string | null>;
  getUserInfo?: () => Promise<{ sub?: string; id?: string; email?: string; [key: string]: any } | null>;
  getEnvVars?: () => Record<string, string>;
  [key: string]: any;
}

interface MCPAgentClientType {
  login: (userId: string, token: string) => Promise<boolean>;
  processRequest: (requestData: any, options?: any) => Promise<any>;
  [key: string]: any;
}
// --- END TYPE DEFINITIONS ---

// --- ADDED: Local definitions for MCP Callback types --- 
interface MCPProgressData {
  query_id?: string;
  update_type: string;
  agent?: string;
  message?: string;
  timestamp?: number;
  [key: string]: any; // Allow other fields
}

interface MCPCompletionData {
  query_id?: string;
  update_type: string;
  result?: string;
  session_id?: string;
  timestamp?: number;
  [key: string]: any; // Allow other fields
}

interface MCPErrorData {
  query_id?: string;
  update_type: string;
  message?: string;
  error?: string;
  timestamp?: number;
  [key: string]: any; // Allow other fields
}
// --- END ADDED ---

/**
 * MainWindow - Main chat interface of the application
 * 
 * This component is responsible for:
 * - Displaying conversation list via SideMenu
 * - Showing the current conversation's messages
 * - Handling message sending via InputBox
 * - Managing chat state and real-time updates
 * - Orchestrating agent-based responses using MCP Agent
 */

// Constants
const NAVBAR_HEIGHT = 64;

const MainWindowNew: React.FC = () => {
  console.log('[MainWindowNew] component mounted');
  const theme = useTheme();
  const { conversation, file, network } = useMainWindowHooks();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  const { getAccessToken } = useAuth();
  
  // State for UI management
  const [isSideMenuOpen, setIsSideMenuOpen] = useState(!isMobile);
  const [alertOpen, setAlertOpen] = useState(false);
  const [alertMessage, setAlertMessage] = useState('');
  const [alertSeverity, setAlertSeverity] = useState<AlertColor>('info');
  
  // State for MCP Agent
  const [mcpAgentClient, setMcpAgentClient] = useState<any>(null);
  const [progressUpdates, setProgressUpdates] = useState<Record<string, string>>({});
  const [activeAgents, setActiveAgents] = useState<Record<string, boolean>>({});
  const [currentUserId, setCurrentUserId] = useState<string | null>(null);
  
  // User info caching is now handled by the global cache utility
  
  // Get database utilities for message persistence
  const { saveMessageToDatabase } = useMessageDatabaseUtils();
  
  // State for real-time update 
  const [activeQueryId, setActiveQueryId] = useState<string | null>(null);
  
  // Initialize real-time updates hook
  const realTimeUpdates = useRealTimeUpdates();
  
  // --- UPDATED: Extract SCOPED state and functions from useRealTimeUpdates --- 
  const {
    isAnyQueryProcessing,  // This is now SCOPED isLoading for the current conversation
    humanInputRequest,     // This is now SCOPED humanInputRequest for the current conversation
    isWaitingForClarification, // Get the new flag
    submitHumanInput,
    cancelHumanInput,
    // ... other functions/values returned by the hook if needed ...
    handleCoordinatorResponse, // Keeping necessary functions
    connectToWebSocket,
    cleanupQueryResources
  } = realTimeUpdates;

  // Create stable callback refs to avoid dependency issues
  const handleAgentProgressRef = useRef<(update: MCPProgressData) => void>();
  const handleAgentCompletedRef = useRef<(response: MCPCompletionData) => void>();  
  const handleAgentErrorRef = useRef<(error: { message: string }) => void>();

  // Define the actual callback functions that can access current state
  handleAgentProgressRef.current = (update: MCPProgressData) => {
    console.log('MCP Agent progress update:', update);
    const agentName = update.agent || 'UnknownAgent';
    setProgressUpdates(prev => ({ ...prev, [agentName]: update.message || '' }));
    setActiveAgents(prev => ({ ...prev, [agentName]: true }));
  };

  handleAgentCompletedRef.current = (response: MCPCompletionData) => {
    console.log('MCP Agent completed:', response);
    const resultText = response.result || '';
    const currentConvId = conversation.currentConversationId;
    if (currentConvId) {
      conversation.addMessage(currentConvId, {
        id: `agent-${Date.now()}`,
        content: resultText,
        role: 'assistant',
        timestamp: new Date(),
      });
    }
    setProgressUpdates({});
    setActiveAgents({});
  };

  handleAgentErrorRef.current = (error: { message: string }) => {
    console.error('MCP Agent error:', error);
    
    const currentConvId = conversation.currentConversationId;
    if (currentConvId) {
      conversation.addMessage(currentConvId, {
        id: `error-${Date.now()}`,
        content: `Error: ${error.message}`,
        role: 'assistant' as const,
        timestamp: new Date(),
      });
    }
    
    setProgressUpdates({});
    setActiveAgents({});
    
    setAlertMessage(`Agent error: ${error.message}`);
    setAlertSeverity('error');
    setAlertOpen(true);
  };

  // Stable wrapper functions that never change
  const handleAgentProgress = useCallback((update: MCPProgressData) => {
    handleAgentProgressRef.current?.(update);
  }, []);

  const handleAgentCompleted = useCallback((response: MCPCompletionData) => {
    handleAgentCompletedRef.current?.(response);
  }, []);

  const handleAgentError = useCallback((error: { message: string }) => {
    handleAgentErrorRef.current?.(error);
  }, []);

  // Toggle side menu
  const toggleSideMenu = useCallback(() => {
    setIsSideMenuOpen(prev => !prev);
  }, []);
  
  // Utility function to safely access Electron APIs with fallbacks
  const getElectronAPI = useCallback(() => {
    // Check if we are in Electron environment
    const isElectron = window.electron !== undefined;
    console.log('Environment check: Running in Electron?', isElectron);
    
    // Return a proxy that provides fallbacks for missing Electron APIs
    return {
      async getApiUrl() {
        if (isElectron && window.electron && window.electron.getApiUrl) {
          return window.electron.getApiUrl();
        }
        // Fallback to environment variable or default
        return import.meta.env.VITE_API_URL || 'http://localhost:8001/api/v1';
      },
      
      async getApiKey() {
        if (isElectron && window.electron && window.electron.getApiKey) {
          return window.electron.getApiKey();
        }
        // Fallback to environment variable or empty string
        return import.meta.env.VITE_API_KEY || '';
      },
      
      onSelectedOption(callback: (option: any) => void) {
        if (isElectron && window.electron && window.electron.onSelectedOption) {
          return window.electron.onSelectedOption(callback);
        }
        // Return no-op cleanup function for browser mode
        return () => {};
      }
    };
  }, []);
  
  // Create electron API wrapper
  const electronAPI = getElectronAPI();
  
  // NOTE: Conversation initialization is now handled by useConversationList hook
  // which has proper Zustand persistence and prevents race conditions
  
  // Handle selected option from subwindow (Electron specific)
  useEffect(() => {
    const handleSelectedOption = async (option: any) => {
      // --- Get current conversation ID --- 
      let targetConversationId = conversation.currentConversationId;
      if (!targetConversationId) {
        console.error('[handleSelectedOption] No current conversation ID found. Cannot proceed.');
        setAlertMessage('Please select or start a conversation first.');
        setAlertSeverity('warning');
        setAlertOpen(true);
        return;
      }
      
      try {
        // --- Step 1: Send user message (as requested) ---
        const processedOption = {
          id: String(option.id),
          title: String(option.title || ''),
          description: String(option.description || '')
        };
        console.log('🎯 Received selected option in main window:', processedOption);

        const userMessage: Message = {
          id: `user-${uuidv4()}`,
          content: processedOption.title, // Use the option title as the user message content
          role: 'user',
          timestamp: new Date(),
          files: [], // No files attached for selected option flow
        };
        await conversation.addMessage(targetConversationId, userMessage);
        // Optional: Save this user message to DB if desired
        // await saveMessageToDatabase(targetConversationId, userMessage.content, 'user');

        // --- Step 2: Generate queryId --- 
        const queryId = `query-${uuidv4()}`;
        console.log(`[handleSelectedOption] Generated queryId: ${queryId}`);

        // --- Step 3: Establish WebSocket Connection (like handleSendMessage) ---
        console.log(`[handleSelectedOption] Connecting WebSocket for queryId: ${queryId}`);
        realTimeUpdates.connectToWebSocket(queryId, targetConversationId);

        // --- Step 4: Call MCP Agent Client --- 
        console.log('[handleSelectedOption] Making MCP coordinator API call with MCP Agent Client...');
        if (mcpAgentClient) {
          try {
            // Pass `processedOption` as the first argument.
            // mcpAgentClient will detect its shape (`id` and `title`) and internally set:
            // - query: processedOption.title
            // - description: processedOption.description
            // - fromIntentionAgent: true
            const result = await mcpAgentClient.processRequest(processedOption, { // Pass option object directly
              realtime: true, // Essential for WebSocket updates
              query_id: queryId, // Pass the generated queryId
              conversation_id: targetConversationId
              // No need to pass from_intention_agent here, client infers it
            });
            
            console.log('[handleSelectedOption] MCP Agent Client initial result (HTTP response):', result);
            
            // Handle immediate errors from the HTTP call (e.g., server unavailable)
            if (result && !result.success && result.error) {
              console.log('[handleSelectedOption] MCP Agent Client HTTP request failed:', result);
              conversation.addMessage(targetConversationId, {
                id: `error_${Date.now()}`,
                content: result.message || "Sorry, I couldn't initiate the request properly.", 
                role: 'assistant',
                timestamp: new Date()
              });
              // Clean up WebSocket resources if the initial call failed
              realTimeUpdates.cleanupQueryResources(queryId);
            } 
            // If successful, wait for updates via WebSocket handlers...

          } catch (agentError) { // Catch errors from mcpAgentClient.processRequest
            console.error('[handleSelectedOption] Error calling MCP Agent Client processRequest:', agentError);
            const errorMessage = agentError instanceof Error ? agentError.message : String(agentError);
            setAlertMessage(`Failed to process selected option: ${errorMessage}`);
            setAlertSeverity('error');
            setAlertOpen(true);
            // Clean up WebSocket resources on error
            realTimeUpdates.cleanupQueryResources(queryId);
            
            // Fallback logic remains the same (and still has WebSocket issues)
            console.log('⚠️ Falling back to direct API call... (Manual WebSocket handling would be required here)');
            const directQueryId = `query_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`; // Fallback needs its own ID
            const requestBody = {
              query_id: directQueryId, 
              context: {
                query: processedOption.title, 
                description: processedOption.description,
                source: 'selected_option_fallback',
                option_id: processedOption.id,
                // Explicitly set flag for fallback, as client isn't used
                from_intention_agent: true 
              }
            };
            try {
              const responseData = await api.processMCPCoordinator(requestBody);
              console.log('✅ Fallback API response:', responseData.data);
              if (targetConversationId) {
                await realTimeUpdates.handleCoordinatorResponse(responseData.data, targetConversationId);
              }
            } catch (fallbackError) {
              console.error('❌ Error during fallback API call:', fallbackError);
            }
          }
        } else {
          // MCPAgentClient not available
          console.log('⚠️ MCP Agent Client not available, using direct API... (Manual WebSocket handling would be required here)');
          const directQueryId = `query_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
          const requestBody = {
            query_id: directQueryId,
            context: {
              query: processedOption.title,
              description: processedOption.description,
              source: 'selected_option_no_client',
              option_id: processedOption.id,
              from_intention_agent: true
            }
          };
          try {
            const responseData = await api.processMCPCoordinator(requestBody);
            console.log('✅ Direct API response:', responseData.data);
            if (targetConversationId) {
              await realTimeUpdates.handleCoordinatorResponse(responseData.data, targetConversationId);
            }
          } catch (directApiError) {
             console.error('❌ Error during direct API call:', directApiError); 
          }
        }
        
      } catch (err) { // Catch errors in the outer try block (e.g., processing option, adding message)
        console.error('[handleSelectedOption] Outer error handling selected option:', err);
        const errorMessage = err instanceof Error ? err.message : String(err); 
        setAlertMessage(`Failed to process selected option: ${errorMessage}`);
        setAlertSeverity('error');
        setAlertOpen(true);
      }
    };

    const unsubscribe = electronAPI.onSelectedOption(handleSelectedOption);
    return unsubscribe;
  }, [conversation, electronAPI, mcpAgentClient, realTimeUpdates.handleCoordinatorResponse]);
  
  // Handle network status changes
  useEffect(() => {
    if (network.isOffline && !alertOpen) {
      setAlertMessage('You appear to be offline. Some features may not work properly.');
      setAlertSeverity('warning');
      setAlertOpen(true);
    }
  }, [network.isOffline]); // Removed alertOpen dependency to prevent state update loops
  
  // Initialize MCP Agent client
  useEffect(() => {
    const initializeAgentClient = async () => {
       if (mcpAgentClient) {
         console.log('[MainWindowNew] MCPAgentClient already initialized, skipping.');
         return;
       }

       console.log('[MainWindowNew] Attempting to initialize MCPAgentClient...');
       
       try {
         // Lazy import to avoid issues if the module isn't available
         const MCPAgentClientModule = await import('../utils/mcp-agent-client');
         const MCPAgentClient = MCPAgentClientModule.default;
         
         const newClient = new MCPAgentClient() as any;
        
        const electron = (window as any).electron;
        if (electron && typeof electron.getAccessToken === 'function' && typeof electron.getUserInfo === 'function') {
          console.log('[MainWindowNew] Attempting Electron login for MCPAgentClient...');
          try {
            const token = await getCachedAccessToken(); // Use cached token system
            
            // Use cached user info to prevent repeated Auth0 calls
            const userInfo = await getUserInfoCached();
            
            // Prioritize 'sub', then 'id', then 'email' as a last resort for effectiveUserId
            const effectiveUserId = userInfo?.sub || userInfo?.id || userInfo?.email;

            console.log('[MainWindowNew] Raw userInfo for MCPAgentClient login:', userInfo);
            console.log(`[MainWindowNew] Determined effectiveUserId for MCPAgentClient: ${effectiveUserId}`);

            if (token && userInfo && effectiveUserId) {
              setCurrentUserId(effectiveUserId);
              console.log('[MainWindowNew] Authenticating MCP Agent...');
              const loginSuccess = await newClient.login(effectiveUserId, token);
              console.log(`[MainWindowNew] MCPAgentClient Electron login with userId '${effectiveUserId}' success: ${loginSuccess}`);
              if (!loginSuccess) {
                // Only show alert if this is not during app initialization
                console.warn('MCP Agent authentication failed, but continuing with limited functionality');
                // Don't show alert immediately - wait to see if it's just a startup timing issue
                setTimeout(() => {
                  if (!newClient.isLoggedIn) {
                    setAlertMessage('MCP Agent service is initializing. Some features may be temporarily limited.');
                    setAlertSeverity('info');
                    setAlertOpen(true);
                  }
                }, 3000); // Wait 3 seconds before showing message
              } else {
                console.log('[MainWindowNew] MCP Agent authentication successful');
              }
            } else {
              console.warn('[MainWindowNew] MCPAgentClient Electron login: Missing token, user info, or usable user ID (id/email).');
              // Fallback to dev login if in DEV mode
              if (import.meta.env.DEV) {
                console.log('[MainWindowNew] MCPAgentClient attempting dev mode login as fallback.');
                await newClient._devModeLogin(); 
              }
            }
          } catch (loginError: any) {
            console.error('[MainWindowNew] MCPAgentClient Electron login error:', loginError);
            // Don't show alert for authentication errors during startup - they often resolve themselves
            console.log('MCP Agent authentication will retry automatically');
          }
        } else if (import.meta.env.DEV) {
          // In dev mode (not Electron), the client constructor already called _devModeLogin()
          console.log('[MainWindowNew] MCPAgentClient running in DEV mode (not Electron), constructor handled dev login.');
        }
        
        setMcpAgentClient(newClient);
        console.log('MCP Agent client fully initialized and configured.');
        
      } catch (error) {
        console.error('Failed to initialize MCP Agent client:', error);
        // Only show initialization errors after a delay to avoid startup noise
        setTimeout(() => {
          setAlertMessage('MCP Agent service is starting up. Some features may be temporarily unavailable.');
          setAlertSeverity('info');
          setAlertOpen(true);
        }, 5000); // Wait 5 seconds before showing initialization error
      }
    };
    
    initializeAgentClient();
    
    // Clean up on unmount
    return () => {
      if (mcpAgentClient) {
        try {
          // mcpAgentClient doesn't have a destroy method, so we just log the cleanup
          console.log('Cleaning up MCP Agent client');
          // Just set the reference to null - garbage collection will handle the rest
          setMcpAgentClient(null);
        } catch (error) {
          console.warn('Error during MCP Agent client cleanup:', error);
        }
      }
    };
  }, []); // Remove all dependencies to prevent re-initialization on state changes
  
  // Helper function to handle fallback to standard API
  const fallbackToStandardApi = useCallback(async (text: string, conversationId: string, attachments: any[] = []) => {
    console.log('Using standard API for message handling');
    
    try {
      if (!api.sendMessage) {
        throw new Error('sendMessage API function not available');
      }

      // Make the API call
      const response = await api.sendMessage(text, conversationId, attachments);
      
      // Validate response data structure
      if (!response || !response.data || !response.data.message) {
        throw new Error('Invalid response structure from server');
      }
      const responseMessageData = response.data.message; // Extract message data
      
      // Process response and add to conversation
      const assistantMessage: Message = {
        id: responseMessageData.id || `assistant-${Date.now()}`,
        content: responseMessageData.content,
        role: 'assistant',
        timestamp: new Date(responseMessageData.created_at || Date.now())
      };
      
      await conversation.addMessage(conversationId, assistantMessage);
      console.log('Assistant message added to conversation:', assistantMessage);
    } catch (error) {
      console.error('Standard API request failed:', error);
      
      // Show error in chat
      const errorMessage: Message = {
        id: `error-${Date.now()}`,
        content: `Sorry, I couldn't process your request. ${error instanceof Error ? error.message : 'Please try again later.'}`,
        role: 'assistant' as const,
        timestamp: new Date()
      };
      
      await conversation.addMessage(conversationId, errorMessage);
      throw error; // Re-throw to trigger the main error handler
    } finally {
      // Loading state is now managed by useRealTimeUpdates
    }
  }, [conversation]);
  
  // Handle sending a message
  const handleSendMessage = useCallback(async (content: string, files?: File[], mode?: 'multiagent' | 'single', singleAgentType?: string) => {
    console.log('[MainWindowNew] handleSendMessage ENTERED', { content: content?.substring(0,50), fileCount: files?.length, mode, singleAgentType });
    if (!content.trim() && (!files || files.length === 0)) return;
    if (conversation.isLoading) return;
    
    console.log('[MainWindowNew] handleSendMessage called with:', { content, files, mode, singleAgentType });
    
    let targetConversationId = conversation.currentConversationId;
    if (!targetConversationId) {
      try {
        console.log('[MainWindowNew] No current conversation, creating a new one...');
        targetConversationId = await conversation.createConversation('New Conversation');
        conversation.setCurrentConversationId(targetConversationId);
      } catch (error) {
        console.error('[MainWindowNew] Failed to create a new conversation:', error);
        setAlertMessage('Failed to create a new conversation. Please try again.');
        setAlertSeverity('error');
        setAlertOpen(true);
        return;
      }
    }
    
    if (!targetConversationId) {
      console.error("[MainWindowNew] Cannot proceed without a targetConversationId after attempting creation.");
      setAlertMessage('Failed to establish a conversation context. Please try again.');
      setAlertSeverity('error');
      setAlertOpen(true);
      return;
    }

    const userMessageId = `user-${uuidv4()}`;
    const queryId = `query-${uuidv4()}`;
    const currentTime = new Date();
    let fileAttachments: FileAttachment[] = [];
    let finalFileIds: string[] = [];
    let uploadErrorOccurred = false;

    if (files && files.length > 0) {
      fileAttachments = files.map(file => ({
        id: `temp-${uuidv4()}`,
              name: file.name,
              size: file.size,
              type: file.type,
        url: '',
              isUploading: true,
        status: 'uploading'
      }));
    }

      const userMessage: Message = {
      id: userMessageId,
        content: content.trim(),
        role: 'user',
      timestamp: currentTime,
        files: fileAttachments,
      };
      await conversation.addMessage(targetConversationId, userMessage);
    if (targetConversationId) {
      await saveMessageToDatabase(targetConversationId, userMessage.id, userMessage.content, 'user', { file_ids: [] });
    }

    if (files && files.length > 0) {
      console.log(`[MainWindowNew] Uploading ${files.length} files for message ${userMessageId} with queryId ${queryId}`);
      const uploadPromises = files.map((file, index) => 
        api.uploadFile(file, { 
          query_id: queryId, 
          message_id: userMessageId,
          user_id: currentUserId
        })
          .then((uploadResponse: { id: string, url?: string }) => {
            const realFileId = uploadResponse.id;
            console.log(`[MainWindowNew] Upload success for ${file.name}: ${realFileId}`);
            const updatedAttachment: FileAttachment = {
              // Use the initial temporary attachment as base
              ...fileAttachments[index], 
              id: realFileId, 
              url: uploadResponse.url || `/api/v1/files/${realFileId}/download`,
              isUploading: false,
              status: 'completed',
              isActive: true,
            };
            // Return success status and the final UI data for this file
            return { success: true, id: realFileId, uiData: updatedAttachment }; 
          })
          .catch((error: any) => {
            console.error(`[MainWindowNew] Upload failed for ${file.name}:`, error);
            uploadErrorOccurred = true;
            const errorAttachment: FileAttachment = {
               // Use the initial temporary attachment as base
               ...fileAttachments[index],
               isUploading: false,
               hasError: true,
               status: 'error',
               errorMessage: error.message || 'Upload failed',
               isActive: false,
            };
             // Return failure status and the error UI data for this file
            return { success: false, id: null, uiData: errorAttachment }; 
          })
      );

      console.log('[MainWindowNew] Awaiting upload promises...');
      const uploadResults = await Promise.all(uploadPromises);
      console.log('[MainWindowNew] Upload promises resolved.', uploadResults);
      console.log(`[MainWindowNew] Checking uploadErrorOccurred flag: ${uploadErrorOccurred}`);
      
      // --- MOVED: Update message state ONCE after all uploads complete --- 
      const finalUiAttachments = uploadResults.map((r: { uiData: FileAttachment }) => r.uiData);
      if (targetConversationId) {
        console.log('[MainWindowNew] Updating message UI with final file statuses...');
        await conversation.updateMessage(targetConversationId, userMessageId, { files: finalUiAttachments });
      }
      // --- END MOVED ---
      
      finalFileIds = uploadResults.filter((r: { success: boolean }) => r.success).map((r: { id: string | null }) => r.id as string);
      
      if (uploadErrorOccurred) {
          console.error('[MainWindowNew] One or more file uploads failed. Aborting agent call.');
          setAlertMessage('Failed to upload one or more files. Please try again.');
          setAlertSeverity('error');
          setAlertOpen(true);
          if (targetConversationId) {
              await saveMessageToDatabase(targetConversationId, userMessage.id, userMessage.content, 'user', { file_ids: finalFileIds, uploadError: true });
          }
          return;
      }
      
      if (targetConversationId) {
          await saveMessageToDatabase(targetConversationId, userMessage.id, userMessage.content, 'user', { file_ids: finalFileIds });
      }

      fileAttachments = finalUiAttachments; 

      // Refresh the file list after successful uploads
      if (finalFileIds.length > 0 && !uploadErrorOccurred) {
        console.log('[MainWindowNew] Uploads successful, refreshing file list.');
        file.loadFiles(); // Corrected to use file.loadFiles()
      }
    }

    try { 
        if (!targetConversationId) {
            throw new Error("Cannot process agent request without a valid conversation ID.");
        }
      if (mcpAgentClient) {
        console.log('[MainWindowNew] Processing with MCP Agent Client...');
            const processedAttachments = await Promise.all(fileAttachments.filter(att => !att.hasError).map(async attachment => {
            const isImage = attachment.type?.startsWith('image/');
            const result = { id: attachment.id, name: attachment.name, type: attachment.type, size: attachment.size, file_id: attachment.id };
              if (isImage && files) { 
                const originalFile = files.find(f => f.name === attachment.name && f.size === attachment.size);
                if (originalFile) {
              try {
                    console.log(`[MainWindowNew] Converting image to base64: ${attachment.name}`);
                const reader = new FileReader();
                    const base64Data = await new Promise<string>((resolve, reject) => {
                  reader.onloadend = () => resolve(reader.result as string);
                      reader.onerror = (err) => {
                        console.error('[MainWindowNew] FileReader error:', err);
                        reject(err); 
                      };
                      reader.readAsDataURL(originalFile);
                });
                    console.log(`[MainWindowNew] Image conversion success: ${attachment.name}`);
                return { ...result, data: base64Data.split(',')[1], mimeType: attachment.type };
              } catch (error) {
                    console.error(`[MainWindowNew] Failed to convert image ${attachment.name} to base64 (in catch): ${error}`);
                    return result;
                  }
                } else {
                   console.warn(`[MainWindowNew] Could not find original File object for image: ${attachment.name}`);
                return result;
              }
            }
            return result;
          }));
          
            console.log('[MainWindowNew] Attempting agent call...', { queryId, targetConversationId });
            console.log('[MainWindowNew] Processed Attachments Payload:', JSON.stringify(processedAttachments));
          
          console.log(`[MainWindowNew] Passing queryId to MCP agent: ${queryId}`);
          
            // --- ADDED: Log before WebSocket connection attempt ---
            console.log(`[MainWindowNew] PRE-CONNECT CHECK - TargetConversationId: ${targetConversationId}, QueryId: ${queryId}`);
            // --- END ADDED ---
            if (targetConversationId) { 
          // --- MOVED: Connect WebSocket AFTER initiating the request --- 
          // realTimeUpdates.connectToWebSocket(queryId, targetConversationId);
          
          const agentResult = await mcpAgentClient.processRequest(content, {
            realtime: true,
            query_id: queryId, 
            attachments: processedAttachments,
            conversation_id: targetConversationId,
            mode: mode || 'multiagent',
            single_agent_type: mode === 'single' ? singleAgentType : undefined,
          });
          
          // --- ADDED: Connect WebSocket AFTER initiating the request --- 
          console.log(`[MainWindowNew] Initiated agent request for ${queryId}. Now connecting WebSocket.`);
          realTimeUpdates.connectToWebSocket(queryId, targetConversationId);
          // --- END ADDED ---
          
          console.log('[MainWindowNew] MCP Agent Client initial result (may be empty if using WebSocket):', agentResult);
          
          if (agentResult && !agentResult.success && agentResult.error) {
            console.log('[MainWindowNew] MCP Agent returned an immediate error:', agentResult);
                    if(targetConversationId){
            await conversation.addMessage(targetConversationId, {
              id: `error_${Date.now()}`,
              content: agentResult.result || "Sorry, I couldn't process your request properly.",
              role: 'assistant',
              timestamp: new Date()
            });
                    }
            realTimeUpdates.cleanupQueryResources(queryId);
                }
            }
        } else {
            console.log('[MainWindowNew] MCP Client not available, using regular API...');
            if (targetConversationId) { 
                await fallbackToStandardApi(content, targetConversationId, fileAttachments);
            }
          }
        } catch (agentError) {
          console.error('[MainWindowNew] MCP Agent processing failed, falling back to regular API:', agentError);
          console.error('[MainWindowNew] Error occurred during mcpAgentClient.processRequest or subsequent handling.', agentError);
          const errorMessage = agentError instanceof Error ? agentError.message : String(agentError);
          setAlertMessage(`Error: ${errorMessage}`);
          setAlertSeverity('error');
          setAlertOpen(true);
          
          try {
            console.log('[MainWindowNew] Falling back to regular API...');
            console.log(`[MainWindowNew] Calling fallbackToStandardApi with content: "${content.substring(0,50)}...", convId: ${targetConversationId}, attachments:`, fileAttachments);
            if (targetConversationId) { 
            await fallbackToStandardApi(content, targetConversationId, fileAttachments);
            }
          } catch (apiError) {
            console.error('[MainWindowNew] Regular API also failed:', apiError);
            if(targetConversationId){
            await conversation.addMessage(targetConversationId, {
              id: `error_fallback_${Date.now()}`,
              content: `Sorry, an error occurred while processing your request via the fallback API. ${apiError instanceof Error ? apiError.message : 'Please try again later.'}`,
              role: 'assistant',
              timestamp: new Date()
            });
          }
        }
    }
  }, [conversation, mcpAgentClient, activeQueryId, realTimeUpdates, saveMessageToDatabase, fallbackToStandardApi, isWaitingForClarification, currentUserId]);
  
  // Reset network status (useful when recovering from errors)
  const handleResetNetwork = useCallback(() => {
    window.resetCircuitBreaker?.();
    conversation.clearLoadedConversationsCache();
    
    if (conversation.currentConversationId) {
      conversation.loadConversation(conversation.currentConversationId);
    }
    
    setAlertMessage('Network connection reset');
    setAlertSeverity('info');
    setAlertOpen(true);
  }, [conversation]);
  
  // Handle alert close
  const handleAlertClose = () => {
    setAlertOpen(false);
  };
  
  // Get conversation messages for chat area - prevent flashing by maintaining previous messages during loading
  const messages = useMemo(() => {
    if (!conversation.currentConversationId) return [];
    
    const currentConversation = conversation.conversationList.find(
      (c: any) => c.id === conversation.currentConversationId
    );
    
    // If no current conversation data exists, return empty array (initial state)
    if (!currentConversation || !conversation.currentConversation) return [];
    
    // Safety check: ensure messages array exists
    const messagesArray = conversation.currentConversation.messages || [];
    const hasMessages = messagesArray.length > 0;
    
    console.log('📄 Current messages for rendering:', {
      conversationId: conversation.currentConversationId,
      messageCount: messagesArray.length,
      hasMessages,
      isLoading: conversation.isLoading,
      messageRoles: messagesArray.map((m: any) => m.role),
      messageIds: messagesArray.map((m: any) => m.id.substring(0, 8))
    });
    
    return messagesArray;
  }, [conversation.currentConversationId, conversation.currentConversation, conversation.conversationList, conversation.isLoading]);
  
  // --- ADDED: Log messages being passed to ChatArea ---
  useEffect(() => {
    if (messages && messages.length > 0) {
      console.log("🩺 MainWindowNew - Messages passed to ChatArea:", 
        JSON.stringify(messages.map(m => ({ 
          id: m.id, 
          role: m.role, 
          contentPreview: typeof m.content === 'string' ? m.content.substring(0, 20) + '...' : '[complex content]',
          fileCount: m.files?.length || 0, 
          files: m.files // Log the actual files array 
        })), null, 2) // Use JSON.stringify for better object inspection
      );
    }
  }, [messages]);
  // --- END ADDED ---
  
  // Effect to update conversation title when messages change in a new conversation
  useEffect(() => {
    if (!conversation.currentConversationId || !conversation.currentConversation) {
      return;
    }
    
    const currentConv = conversation.currentConversation;
    const messages = currentConv.messages || [];
    
    const userMessages = messages.filter(msg => msg.role === 'user');
    if (userMessages.length === 1 && currentConv.title === 'New Conversation') {
      const userMessage = userMessages[0];
      const content = typeof userMessage.content === 'string' ? userMessage.content : String(userMessage.content || '');
      const newTitle = content.length > 30 
        ? `${content.substring(0, 30)}...` 
        : content;
      
      console.log('Updating conversation title for new conversation:', newTitle);
      conversation.updateTitle(newTitle);
    }
  }, [conversation.currentConversationId, conversation.currentConversation]);
  
  // --- ADDED: Stop Processing Handler --- 
  const handleStopProcessing = useCallback(async () => {
    const queryIdToStop = realTimeUpdates.activeQueryId;
    console.log(`[MainWindowNew] Requesting stop for query: ${queryIdToStop}`);
    if (queryIdToStop) {
        try {
          // Call the cancel API endpoint
          console.log(`[MainWindowNew] Calling API to cancel query: ${queryIdToStop}`);
          const result = await api.cancelQuery(queryIdToStop);
          console.log(`[MainWindowNew] Successfully cancelled query:`, result);
        } catch (error) {
          console.error(`[MainWindowNew] Error calling cancel API:`, error);
        }

        // Immediately clean up frontend resources regardless of API result
        realTimeUpdates.cleanupQueryResources(queryIdToStop);
    }
  }, [realTimeUpdates.activeQueryId, realTimeUpdates.cleanupQueryResources, api]);
  // --- END ADDED ---
  
  // --- ADDED: Function to create a new conversation ---
  const handleCreateNewConversation = useCallback(async () => {
    if (conversation.isLoading) return; // Prevent action while loading
    try {
      console.log('[MainWindowNew] Creating new conversation via NavBar...');
      const newId = await conversation.createConversation('New Conversation');
      conversation.setCurrentConversationId(newId);
      // Optionally close the side menu if it's open, especially on mobile
      if (isMobile && isSideMenuOpen) {
        toggleSideMenu();
      }
    } catch (err) {
      console.error('Failed to create new conversation:', err);
      setAlertMessage('Failed to create new conversation.');
      setAlertSeverity('error');
      setAlertOpen(true);
    }
  }, [conversation, isMobile, isSideMenuOpen, toggleSideMenu]);
  // --- END ADDED ---
  
  // Show less intrusive loading state - only for critical failures
  if (conversation.isConversationError && conversation.conversationListError) {
    return (
      <Box
        display="flex"
        justifyContent="center"
        alignItems="center"
        minHeight="100vh"
      >
        <Alert severity="error">
          Failed to load conversations. Please refresh the page.
        </Alert>
      </Box>
    );
  }
  
  // Get current conversation and messages
  const currentConversationData = conversation.currentConversation;
  
  // Debug current conversation state
  console.log('🗨️ MainWindowNew current conversation:', {
    conversationId: conversation.currentConversationId,
    hasConversation: !!currentConversationData,
    messageCount: messages.length,
    isLoading: conversation.isLoading,
    showLoadingIndicator: conversation.showLoadingIndicator
  });
  
  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        height: '100vh',
        overflow: 'hidden',
        backgroundColor: theme.palette.background.default,
      }}
    >
      <NavBarNew 
        onToggleSideMenu={toggleSideMenu} 
        title={currentConversationData?.title || 'Chat'}
        onCreateNewConversation={handleCreateNewConversation}
      />
      
      <Box
        sx={{
          display: 'flex',
          flexGrow: 1,
          overflow: 'hidden',
          position: 'relative',
        }}
      >
        <Box
          sx={{
            position: 'absolute',
            zIndex: 10,
            height: '100%',
            left: 0,
            top: 0,
          }}
        >
          <SideMenuNew
            isOpen={isSideMenuOpen}
            isMobile={isMobile}
            setIsOpen={setIsSideMenuOpen}
            navbarHeight={NAVBAR_HEIGHT}
          />
        </Box>
        
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            flexGrow: 1,
            width: '100%',
            overflow: 'hidden',
          }}
        >
          {network.isDegraded && (
            <Box 
              sx={{ 
                bgcolor: 'warning.main', 
                color: 'warning.contrastText',
                py: 0.5,
                px: 2,
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center'
              }}
            >
              <span>Network connection issues detected</span>
              <Button 
                startIcon={<ReplayIcon />}
                variant="contained"
                color="inherit"
                size="small"
                onClick={handleResetNetwork}
                sx={{ color: 'warning.main' }}
              >
                Reset
              </Button>
            </Box>
          )}
          
          <ChatAreaNew 
            messages={messages} 
            isLoading={isAnyQueryProcessing}
            isLoadingMore={conversation.isLoadingMore}
            hasMoreMessages={conversation.hasMoreMessages}
            loadMoreMessages={conversation.loadMoreMessages}
            humanInputRequest={humanInputRequest}
            onHumanInputSubmit={submitHumanInput}
            onHumanInputCancel={cancelHumanInput}
          />
          
          <AgentStatusIndicator />
          
          <Box sx={{ px: 1, pb: 0.5, pt: 0 }}>
            <InputBoxNew 
              onSendMessage={handleSendMessage} 
              isLoading={isAnyQueryProcessing}
              onStopProcessing={handleStopProcessing}
            />
          </Box>
      
  <Snackbar 
    open={alertOpen} 
    autoHideDuration={6000} 
    onClose={handleAlertClose}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
  >
    <Alert 
      onClose={handleAlertClose} 
      severity={alertSeverity}
          sx={{ width: '100%' }}
    >
      {alertMessage}
    </Alert>
  </Snackbar>
        </Box>
      </Box>
    </Box>
  );
};

export default MainWindowNew; 