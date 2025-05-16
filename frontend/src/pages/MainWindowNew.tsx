import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { Box, useTheme, Snackbar, Alert, useMediaQuery, Button, AlertColor } from '@mui/material';
import ReplayIcon from '@mui/icons-material/Replay';
import { v4 as uuidv4 } from 'uuid';

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
import MCPAgentClient from '../utils/mcp-agent-client';

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
  
  // Initialize conversation when component mounts
  useEffect(() => {
    const initialize = async () => {
      if (conversation.isLoading) return;
      
      try {
        console.log('Initializing conversations...');
        
        // Get existing conversations (or create a new one if none exist)
        const existingConversations = await conversation.loadConversations();
        
        if (!existingConversations || existingConversations.length === 0) {
          // Create a new conversation if none exists
          console.log('No existing conversations, creating a new one');
          const newConversationId = await conversation.createConversation('New Conversation');
          conversation.setCurrentConversationId(newConversationId);
        }
      } catch (err) {
        console.error('Failed to initialize:', err);
        setAlertMessage('Failed to initialize conversations');
        setAlertSeverity('error');
        setAlertOpen(true);
      }
    };
    
    if (import.meta.env.DEV) {
      initialize();
    }
  }, [conversation]);
  
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
  }, [network.isOffline, alertOpen]);
  
  // MCPAgent handlers
  const handleAgentProgress = useCallback((update: MCPProgressData) => {
    console.log('MCP Agent progress update:', update);
    const agentName = update.agent || 'UnknownAgent'; // Handle potentially undefined agent
    setProgressUpdates(prev => ({ ...prev, [agentName]: update.message || '' }));
    setActiveAgents(prev => ({ ...prev, [agentName]: true }));
  }, []);
  
  const handleAgentCompleted = useCallback((response: MCPCompletionData) => {
    console.log('MCP Agent completed:', response);
    const resultText = response.result || ''; // Handle potentially undefined result
    if (conversation.currentConversationId) {
      conversation.addMessage(conversation.currentConversationId, {
        id: `agent-${Date.now()}`,
        content: resultText,
        role: 'assistant',
        timestamp: new Date(),
      });
    }
    setProgressUpdates({});
    setActiveAgents({});
  }, [conversation.currentConversationId, conversation.addMessage]);
  
  const handleAgentError = useCallback((error: { message: string }) => {
    console.error('MCP Agent error:', error);
    
    if (conversation.currentConversationId) {
      // Add error message as system message
      conversation.addMessage(conversation.currentConversationId, {
        id: `error-${Date.now()}`,
        content: `Error: ${error.message}`,
        role: 'assistant' as const,
        timestamp: new Date(),
      });
    }
    
    // Clear progress updates and active agents
    setProgressUpdates({});
    setActiveAgents({});
    
    // Loading state is now managed by useRealTimeUpdates
    
    // Show error alert
    setAlertMessage(`Agent error: ${error.message}`);
    setAlertSeverity('error');
    setAlertOpen(true);
  }, [
    conversation.currentConversationId, 
    conversation.addMessage, 
    setAlertMessage, // Keep stable setters
    setAlertSeverity, 
    setAlertOpen
  ]); // Use stable dependencies
  
  // Initialize MCP Agent client
  useEffect(() => {
    const initializeAgentClient = () => {
      try {
        console.log('Initializing MCP Agent client...');
        
        // Pass the handlers to the client
        const client = new MCPAgentClient({
          onProgress: handleAgentProgress, 
          onCompleted: handleAgentCompleted, 
          onError: (error: MCPErrorData) => {
            console.warn('MCP Agent error:', error);
            
            // Handle connection errors with appropriate messages
            const isConnectionError = error.message?.includes('not available') || 
                                     error.message?.includes('connection');
                                     
            if (isConnectionError) {
              setAlertMessage('MCP Agent server is not available. Using standard API processing instead.');
              setAlertSeverity('warning');
              setAlertOpen(true);
            } else {
              // For other errors, use the normal error handler
              handleAgentError({ message: error.message || 'Unknown MCP Agent Error' } as { message: string });
            }
          },
        });
        
        setMcpAgentClient(client);
        console.log('MCP Agent client initialized');
        
        // Log how query IDs will be generated
        console.log('MCP Agent will use query IDs in format: query-{uuid} to ensure consistency with backend');
      } catch (error) {
        console.error('Failed to initialize MCP Agent client:', error);
        setAlertMessage('Failed to initialize MCP Agent. Using standard API processing instead.');
        setAlertSeverity('warning');
        setAlertOpen(true);
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
  }, [handleAgentProgress, handleAgentCompleted, handleAgentError]);
  
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
  const handleSendMessage = useCallback(async (content: string, files?: File[]) => {
    console.log('[MainWindowNew] handleSendMessage ENTERED', { content: content?.substring(0,50), fileCount: files?.length });
    if (!content.trim() && (!files || files.length === 0)) return;
    if (conversation.isLoading) return;
    
    console.log('[MainWindowNew] handleSendMessage called with:', { content, files });
    
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
      await saveMessageToDatabase(targetConversationId, userMessage.content, 'user', { files: [] });
    }

    if (files && files.length > 0) {
      console.log(`[MainWindowNew] Uploading ${files.length} files for message ${userMessageId} with queryId ${queryId}`);
      const uploadPromises = files.map((file, index) => 
        api.uploadFile(file, { query_id: queryId, message_id: userMessageId })
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
              await saveMessageToDatabase(targetConversationId, userMessage.content, 'user', { 
                  file_ids: finalFileIds, 
                  uploadError: true
              });
          }
          return;
      }
      
      if (targetConversationId) {
          await saveMessageToDatabase(targetConversationId, userMessage.content, 'user', { 
              file_ids: finalFileIds
          });
      }

      fileAttachments = finalUiAttachments; 
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
  }, [conversation, mcpAgentClient, activeQueryId, realTimeUpdates, saveMessageToDatabase, fallbackToStandardApi, isWaitingForClarification]);
  
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
  
  // Get conversation messages for chat area
  const messages = useMemo(() => {
    if (!conversation.currentConversationId) return [];
    
    const currentConversation = conversation.conversationList.find(
      (c: any) => c.id === conversation.currentConversationId
    );
    
    if (!currentConversation || !conversation.currentConversation) return [];
    
    console.log('📄 Current messages for rendering:', {
      conversationId: conversation.currentConversationId,
      messageCount: conversation.currentConversation.messages.length,
      messageRoles: conversation.currentConversation.messages.map((m: any) => m.role),
      messageIds: conversation.currentConversation.messages.map((m: any) => m.id.substring(0, 8))
    });
    
    return conversation.currentConversation.messages;
  }, [conversation.currentConversationId, conversation.currentConversation, conversation.conversationList]);
  
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
  const handleStopProcessing = useCallback(() => {
    const queryIdToStop = realTimeUpdates.activeQueryId;
    console.log(`[MainWindowNew] Requesting stop for query: ${queryIdToStop}`);
    if (queryIdToStop) {
        // TODO: Implement backend API call or MCP Agent call to stop the query
        // Example: 
        // if (mcpAgentClient) { 
        //    mcpAgentClient.stopRequest(queryIdToStop);
        // } else { 
        //    api.stopQuery(queryIdToStop).catch(err => console.error("Stop API call failed:", err));
        // }
        console.warn("[MainWindowNew] Backend stop mechanism not implemented yet.");

        // Immediately clean up frontend resources
        realTimeUpdates.cleanupQueryResources(queryIdToStop);
    }
  }, [realTimeUpdates.activeQueryId, realTimeUpdates.cleanupQueryResources]);
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
  
  // Render loading state if not initialized or authenticating
  if (conversation.isLoading && !import.meta.env.DEV) {
    return (
      <Box
        display="flex"
        justifyContent="center"
        alignItems="center"
        minHeight="100vh"
      >
        <Alert severity="info">Loading...</Alert>
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
          
          <InputBoxNew 
            onSendMessage={handleSendMessage} 
            isLoading={isAnyQueryProcessing}
            onStopProcessing={handleStopProcessing}
          />
      
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