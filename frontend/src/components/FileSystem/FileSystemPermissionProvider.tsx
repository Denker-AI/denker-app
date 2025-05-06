import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { useWebSocket } from '../../services/websocketContext';
import FileSystemPermissionModal from './FileSystemPermissionModal';

// Define types for permission requests
export interface FileSystemPermissionRequest {
  operation_id: string;
  operation: string;
  path: string;
  arguments: any;
}

// Define context type
interface FileSystemPermissionContextType {
  currentRequest: FileSystemPermissionRequest | null;
  respondToRequest: (id: string, allow: boolean) => void;
}

// Create context
const FileSystemPermissionContext = createContext<FileSystemPermissionContextType>({
  currentRequest: null,
  respondToRequest: () => {},
});

// Hook for using the context
export const useFileSystemPermission = () => useContext(FileSystemPermissionContext);

// Provider component
export const FileSystemPermissionProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [pendingRequests, setPendingRequests] = useState<FileSystemPermissionRequest[]>([]);
  const [currentRequest, setCurrentRequest] = useState<FileSystemPermissionRequest | null>(null);
  const { connected, sendMessage, lastMessage } = useWebSocket();

  // Process WebSocket messages
  useEffect(() => {
    if (!lastMessage) return;

    try {
      const message = JSON.parse(lastMessage);
      
      // Handle filesystem permission requests
      if (message.update_type === 'filesystem_permission') {
        // Create a standardized permission request object
        const newRequest: FileSystemPermissionRequest = {
          operation_id: message.data.operation_id,
          operation: message.data.operation,
          path: message.data.path || '',
          arguments: message.data.arguments || {}
        };
        
        console.log('Received filesystem permission request:', newRequest);
        setPendingRequests(prev => [...prev, newRequest]);
      }
    } catch (error) {
      console.error('Error processing WebSocket message:', error);
    }
  }, [lastMessage]);

  // Set current request to the first pending request
  useEffect(() => {
    if (pendingRequests.length > 0 && !currentRequest) {
      setCurrentRequest(pendingRequests[0]);
    }
  }, [pendingRequests, currentRequest]);

  // Function to respond to a permission request
  const respondToRequest = (id: string, allow: boolean) => {
    if (!connected) {
      console.error('Cannot respond to request: WebSocket not connected');
      return;
    }

    // Send response through WebSocket
    const response = {
      type: 'filesystem_permission_response',
      operation_id: id,
      approved: allow
    };
    
    console.log('Sending permission response:', response);
    sendMessage(JSON.stringify(response));
    
    // Remove request from pending list
    setPendingRequests(prev => prev.filter(req => req.operation_id !== id));
    
    // If the current request was responded to, clear it
    if (currentRequest && currentRequest.operation_id === id) {
      setCurrentRequest(null);
    }
  };
  
  // Handle timeout (auto-deny)
  const handleTimeout = () => {
    if (currentRequest) {
      respondToRequest(currentRequest.operation_id, false);
    }
  };

  return (
    <FileSystemPermissionContext.Provider value={{ currentRequest, respondToRequest }}>
      {children}
      
      <FileSystemPermissionModal
        isOpen={!!currentRequest}
        request={currentRequest}
        onResponse={respondToRequest}
        onTimeout={handleTimeout}
      />
    </FileSystemPermissionContext.Provider>
  );
};

export default FileSystemPermissionProvider; 