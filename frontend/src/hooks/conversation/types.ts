import { FileAttachment, Message, Conversation } from '../../store/conversationStore';

/**
 * Conversation loading states
 */
export enum ConversationLoadState {
  /** Not loading anything */
  IDLE = 'idle',
  /** Loading in progress */
  LOADING = 'loading',
  /** Successfully loaded */
  LOADED = 'loaded',
  /** Error occurred */
  ERROR = 'error',
  /** Specific network error state */
  NETWORK_ERROR = 'network_error',
  /** Attempting recovery */
  RECOVERING = 'recovering'
}

/**
 * Common state interface for conversations
 */
export interface ConversationState {
  /** Loading state */
  loadState: ConversationLoadState;
  /** Error message if any */
  error: string | null;
}

/**
 * Type for conversation list
 */
export interface ConversationListItem {
  /** Conversation ID */
  id: string;
  /** Conversation title */
  title: string;
  /** Creation date */
  createdAt: Date;
  /** Last update date */
  updatedAt: Date;
  /** Whether the conversation is active */
  isActive: boolean;
  /** Preview of the first message (optional) */
  preview?: string;
  /** Loading state for this specific conversation */
  loadState?: ConversationLoadState;
}

/**
 * Result of sending a message
 */
export interface SendMessageResult {
  /** Whether the message was sent successfully */
  success: boolean;
  /** Conversation ID */
  conversationId: string | null;
  /** Message ID */
  messageId: string | null;
  /** Error message if any */
  error?: string;
}

/**
 * Represents a file attached to a message, including upload state.
 */
export interface FileAttachment {
  id: string;
  name?: string;      // Optional: Load on demand
  size?: number;      // Optional: Load on demand
  type?: string;      // Optional: Load on demand
  url?: string;       // Optional: Construct/load on demand
  isUploading?: boolean; // Keep required if needed for upload UI
  hasError?: boolean;    // Keep required if needed for error UI
  isDeleted?: boolean;  // Optional: Load on demand
  createdAt?: Date;   // Optional: Load on demand
  status?: 'uploading' | 'processing' | 'completed' | 'error'; // Add status from store type
  errorMessage?: string; // Add errorMessage from store type
  isActive?: boolean; // Added from MainWindowNew usage
}

/**
 * Type exported for use in UI components
 */
export type {
  FileAttachment,
  Message,
  Conversation
};

// Define PaginationState here and export
export interface PaginationState {
  isLoadingMore: boolean;
  hasMoreMessages: boolean;
  oldestMessageId: string | null;
}

/**
 * Represents the state of a conversation being loaded or handled.
 */
export interface ConversationState {
  /** Loading state */
  loadState: ConversationLoadState;
  /** Error message if any */
  error: string | null;
} 