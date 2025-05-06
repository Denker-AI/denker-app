# Unified Filesystem UI Integration Guide

This document explains how to integrate the unified filesystem UI components that provide visibility and control over filesystem operations in the chat area.

## Overview

The filesystem UI system consists of:

1. **Permission Management** - Request and respond to permission requests for file operations
2. **Activity Tracking** - Track and display file operations in the UI
3. **Chat Integration** - Display filesystem operations inline in the chat interface

## Installation

All components are located in the `components/FileSystem` directory and can be imported from there.

## Setup

### 1. Add Providers to Your App

Add the filesystem providers to your app, wrapping them around components that need access:

```tsx
import { 
  WebSocketProvider, 
  FileSystemPermissionProvider, 
  FileSystemActivityProvider 
} from './components/FileSystem';

function App() {
  return (
    <WebSocketProvider>
      <FileSystemPermissionProvider>
        <FileSystemActivityProvider>
          <YourAppContent />
        </FileSystemActivityProvider>
      </FileSystemPermissionProvider>
    </WebSocketProvider>
  );
}
```

### 2. Add the ChatFileSystemActivity to Your Chat Component

Add the `ChatFileSystemActivity` component where you want to display filesystem operations:

```tsx
import { ChatFileSystemActivity } from './components/FileSystem';

function ChatMessage({ message }) {
  return (
    <div className="chat-message">
      <div className="message-content">{message.content}</div>
      
      {/* Add filesystem activity display */}
      <ChatFileSystemActivity messageId={message.id} />
    </div>
  );
}
```

## WebSocket Communication

The system requires the backend to send properly formatted WebSocket messages:

### Permission Requests

```json
{
  "update_type": "filesystem_permission",
  "message": "Permission requested for write_file on /path/to/file.txt",
  "timestamp": "2025-04-15T08:30:45.123Z",
  "data": {
    "operation_id": "550e8400-e29b-41d4-a716-446655440000",
    "operation": "write_file",
    "path": "/path/to/file.txt",
    "arguments": {
      "content": "File content..."
    }
  }
}
```

### File Operation Updates

```json
{
  "update_type": "filesystem",
  "message": "New file created: example.txt in /path/to",
  "timestamp": "2025-04-15T08:30:50.456Z",
  "data": {
    "operation": "create",
    "file_path": "/path/to/example.txt",
    "file_name": "example.txt",
    "directory": "/path/to"
  }
}
```

### Tool Usage Updates

```json
{
  "update_type": "step",
  "message": "Reading file...",
  "timestamp": "2025-04-15T08:30:40.789Z",
  "data": {
    "tool": "filesystem-read_file",
    "arguments": "{\"path\":\"/path/to/file.txt\"}"
  }
}
```

## Implementation Details

### Permissions Flow

1. Backend sends `filesystem_permission` message over WebSocket
2. `FileSystemPermissionProvider` displays modal
3. User approves/denies permission
4. Response sent back via WebSocket
5. Backend continues/aborts operation based on response

### Activity Tracking

1. `FileSystemActivityProvider` listens for filesystem messages
2. Creates a chronological log of operations
3. `ChatFileSystemActivity` displays operations in chat
4. User can see status and details of each operation

## Styling

The UI components use Material UI for styling and should adapt to your app's theme. You can customize the appearance by overriding the Material UI theme or adding custom styles.

## Advanced Usage

### Accessing Operations Programmatically

You can access the filesystem operations state from anywhere in your app:

```tsx
import { useFileSystemActivity } from './components/FileSystem';

function MyComponent() {
  const { operations, clearOperations } = useFileSystemActivity();
  
  return (
    <div>
      <p>Total operations: {operations.length}</p>
      <button onClick={clearOperations}>Clear History</button>
    </div>
  );
}
```

### Custom Permission Handling

You can build custom permission UIs by using the permission hook:

```tsx
import { useFileSystemPermission } from './components/FileSystem';

function CustomPermissionUI() {
  const { currentRequest, respondToRequest } = useFileSystemPermission();
  
  if (!currentRequest) return null;
  
  return (
    <div>
      <h3>Permission Required</h3>
      <p>Operation: {currentRequest.operation}</p>
      <p>Path: {currentRequest.path}</p>
      <button onClick={() => respondToRequest(currentRequest.operation_id, false)}>Deny</button>
      <button onClick={() => respondToRequest(currentRequest.operation_id, true)}>Allow</button>
    </div>
  );
}
```

## Troubleshooting

### Permission Requests Not Showing

Ensure your backend is sending properly formatted WebSocket messages with the `update_type` set to `filesystem_permission`.

### Operations Not Tracking

Check the WebSocket connection is established and the message format matches what the `FileSystemActivityProvider` expects.

## Backwards Compatibility

This system is designed to work alongside existing notification systems like `FileCreationNotification` and `FileNotificationContainer`. You can gradually transition to the new system while maintaining backward compatibility.

## Integration Notes

This filesystem activity system is now the sole system for handling file operations and notifications in the application. The previous standalone notification components (`FileCreationNotification` and `FileNotificationContainer`) have been removed in favor of this more integrated approach. 