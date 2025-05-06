import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { useWebSocket } from '../../services/websocketContext';
import { FileSystemOperation, FileSystemOperationType } from './FileSystemActivityLog';
import { useFileSystemPermission } from './FileSystemPermissionProvider';

interface FileSystemActivityContextType {
  operations: FileSystemOperation[];
  clearOperations: () => void;
  approveOperation: (id: string) => void;
  denyOperation: (id: string) => void;
}

const FileSystemActivityContext = createContext<FileSystemActivityContextType>({
  operations: [],
  clearOperations: () => {},
  approveOperation: () => {},
  denyOperation: () => {}
});

export const useFileSystemActivity = () => useContext(FileSystemActivityContext);

interface FileSystemActivityProviderProps {
  children: ReactNode;
}

export const FileSystemActivityProvider: React.FC<FileSystemActivityProviderProps> = ({ children }) => {
  const [operations, setOperations] = useState<FileSystemOperation[]>([]);
  const { connected, sendMessage, lastMessage } = useWebSocket();
  const { respondToRequest } = useFileSystemPermission();

  // Process WebSocket messages
  useEffect(() => {
    if (!lastMessage) return;

    try {
      const message = JSON.parse(lastMessage);
      
      // Handle different types of filesystem messages
      // Extract update_type and data payload
      const updateType = message.update_type;
      const data = message.data || {};
      
      // Handle filesystem operation updates
      if (updateType === 'filesystem') {
        // Extract operation details
        const { operation, file_path, file_name, directory } = data;
        
        // Generate operation for tracking in UI
        const newOperation: FileSystemOperation = {
          id: `fs-${Date.now()}`,
          type: operation as FileSystemOperationType,
          path: file_path || '',
          status: 'completed',
          timestamp: new Date().toISOString(),
          requiresPermission: false
        };
        
        // Add to operations list
        setOperations(prev => [newOperation, ...prev].slice(0, 50)); // Keep last 50 operations
      }
      
      // Handle filesystem permission requests
      else if (updateType === 'filesystem_permission') {
        // Extract operation details
        const { operation_id, operation, path, arguments: args } = data;
        
        // Create details string based on operation type
        let details = '';
        if (operation === 'move_file') {
          details = `Moving from ${args.source} to ${args.destination}`;
        }
        
        // Create operation object
        const newOperation: FileSystemOperation = {
          id: operation_id,
          type: operation as FileSystemOperationType,
          path: path || '',
          status: 'pending',
          timestamp: new Date().toISOString(),
          details,
          requiresPermission: true
        };
        
        // Add to operations list
        setOperations(prev => [newOperation, ...prev].slice(0, 50));
      }
      
      // Handle general operation updates (read, search, list)
      else if (updateType === 'step' && data.tool && data.tool.startsWith('filesystem-')) {
        // Extract tool name and convert to operation type
        const toolName = data.tool.replace('filesystem-', '');
        const operationType = toolName as FileSystemOperationType;
        
        // Create details based on operation arguments
        let path = '';
        let details = '';
        
        if (data.arguments) {
          try {
            const args = JSON.parse(data.arguments);
            path = args.path || '';
            
            if (operationType === 'search_files') {
              details = `Query: ${args.pattern || 'unknown'}`;
            }
          } catch (e) {
            console.error('Error parsing arguments:', e);
          }
        }
        
        // Create operation object
        const newOperation: FileSystemOperation = {
          id: `fs-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`,
          type: operationType,
          path,
          status: 'completed',
          timestamp: new Date().toISOString(),
          details,
          requiresPermission: false
        };
        
        // Add to operations list if we have a valid path
        if (path) {
          setOperations(prev => [newOperation, ...prev].slice(0, 50));
        }
      }
    } catch (error) {
      console.error('Error processing WebSocket message:', error);
    }
  }, [lastMessage]);

  // Clear all operations
  const clearOperations = () => {
    setOperations([]);
  };

  // Approve a pending operation
  const approveOperation = (id: string) => {
    // Find the operation
    const operation = operations.find(op => op.id === id);
    if (!operation) return;
    
    // Update operation status
    setOperations(prev => 
      prev.map(op => 
        op.id === id 
          ? { ...op, status: 'approved', isPending: true } 
          : op
      )
    );
    
    // Send approval message through permission provider
    respondToRequest(id, true);
    
    // Update status after a delay to show completion
    setTimeout(() => {
      setOperations(prev => 
        prev.map(op => 
          op.id === id 
            ? { ...op, status: 'completed', isPending: false } 
            : op
        )
      );
    }, 1000);
  };

  // Deny a pending operation
  const denyOperation = (id: string) => {
    // Find the operation
    const operation = operations.find(op => op.id === id);
    if (!operation) return;
    
    // Update operation status
    setOperations(prev => 
      prev.map(op => 
        op.id === id 
          ? { ...op, status: 'denied' } 
          : op
      )
    );
    
    // Send denial message through permission provider
    respondToRequest(id, false);
  };

  return (
    <FileSystemActivityContext.Provider 
      value={{ 
        operations, 
        clearOperations, 
        approveOperation, 
        denyOperation 
      }}
    >
      {children}
    </FileSystemActivityContext.Provider>
  );
};

export default FileSystemActivityProvider; 