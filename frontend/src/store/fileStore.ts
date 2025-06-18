import { create, StateCreator, StoreApi } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';

export interface FileItem {
  id: string;
  filename: string;
  fileType: string;
  fileSize: number;
  storagePath: string;
  createdAt: Date;
  isProcessed: boolean;
  isDeleted?: boolean;
  metadata: any;
}

// Explicitly define the type for the store's actions and state
export interface FileStoreState {
  files: FileItem[];
  selectedFileIds: string[];
  _hasHydrated: boolean;
  _rehydrationError: string | null;
}
  
export interface FileStoreActions {
  setFiles: (files: FileItem[]) => void;
  addFile: (file: FileItem) => void;
  updateFile: (id: string, updates: Partial<FileItem>) => void;
  deleteFile: (id: string) => void;
  setHasHydrated: (status: boolean) => void;
  selectFile: (id: string) => void;
  deselectFile: (id: string) => void;
  toggleFileSelection: (id: string) => void;
  clearSelection: () => void;
  getSelectedFiles: () => FileItem[];
  clearRehydrationError: () => void;
  
  // User management methods
  switchUser: (userId: string | null) => void;
  getCurrentUserId: () => string | null;
}

export type FileStore = FileStoreState & FileStoreActions;

// Store the current user ID to detect user changes
let currentFileUserId: string | null = null;

const useFileStore = create<FileStore>()(
  persist(
    (set, get) => ({
      files: [],
      selectedFileIds: [],
      _hasHydrated: false,
      _rehydrationError: null,
      
      setFiles: (files) => set({ files }),
      
      addFile: (file) => set((state) => ({
        files: [...(state.files || []), file]
      })),
      
      updateFile: (id, updates) => set((state) => ({
        files: (state.files || []).map((file) =>
          file.id === id ? { ...file, ...updates } : file
        )
      })),
      
      deleteFile: (id) => set((state) => ({
        files: (state.files || []).filter((file) => file.id !== id),
        selectedFileIds: (state.selectedFileIds || []).filter((fileId) => fileId !== id)
      })),

      setHasHydrated: (status) => set({ _hasHydrated: status }),
      
      selectFile: (id) => set((state) => ({
        selectedFileIds: [...(state.selectedFileIds || []), id]
      })),
      
      deselectFile: (id) => set((state) => ({
        selectedFileIds: (state.selectedFileIds || []).filter((fileId) => fileId !== id)
      })),
      
      toggleFileSelection: (id) => set((state) => ({
        selectedFileIds: (state.selectedFileIds || []).includes(id)
          ? (state.selectedFileIds || []).filter((fileId) => fileId !== id)
          : [...(state.selectedFileIds || []), id]
      })),
      
      clearSelection: () => set({ selectedFileIds: [] }),
      
      getSelectedFiles: () => {
        const state = get();
        return (state.files || []).filter((file) => (state.selectedFileIds || []).includes(file.id));
      },

      clearRehydrationError: () => set({ _rehydrationError: null }),
      
      // User management methods
      switchUser: (userId: string | null) => {
        console.log('[FileStore] Switching user from', currentFileUserId, 'to', userId);
        if (currentFileUserId !== userId) {
          currentFileUserId = userId;
          // Clear current state when switching users
          set({
            files: [],
            selectedFileIds: [],
            _hasHydrated: false,
            _rehydrationError: null,
          });
          // Trigger rehydration for new user - set hydration after brief delay to allow storage name change
          if (userId) {
            console.log('[FileStore] User switched, will load data for user:', userId);
            setTimeout(() => {
              console.log('[FileStore] Setting hydrated flag after user switch');
              set({ _hasHydrated: true, _rehydrationError: null });
            }, 50);
          }
        }
      },
      
      getCurrentUserId: () => currentFileUserId,
    }),
    {
      name: () => currentFileUserId ? `denker-file-storage-${currentFileUserId}` : 'denker-file-storage-temp',
      storage: createJSONStorage(() => localStorage),
      partialize: (state: FileStore) => ({
        files: state.files,
        selectedFileIds: state.selectedFileIds
      }),
      onRehydrateStorage: () => {
        return (state?: FileStoreState, error?: Error | null): void => {
          console.log('[FileStore] Starting rehydration process...');
          
          if (error) {
            console.error('[FileStore] Rehydration error occurred:', error);
            // Modify state directly instead of calling setState
            if (state) {
              state.files = [];
              state.selectedFileIds = [];
              state._hasHydrated = true;
              state._rehydrationError = `Storage rehydration failed: ${error.message}`;
            }
            return;
          }
          
          if (!state) {
            console.log('[FileStore] No state found in storage, setting hydrated flag for new user');
            // For new users with no stored data, we still need to set hydrated flag
            // Use setTimeout to ensure this runs after the store is fully initialized
            setTimeout(() => {
              const currentState = useFileStore.getState();
              if (!currentState._hasHydrated) {
                useFileStore.setState({ _hasHydrated: true, _rehydrationError: null });
                console.log('[FileStore] Hydration flag set for new user');
              }
            }, 10);
            return;
          }
          
          try {
            let processedFiles = [];
            
            if (state.files && Array.isArray(state.files)) {
              processedFiles = state.files.map((file: FileItem) => ({
                ...file,
                createdAt: file.createdAt instanceof Date ? file.createdAt : new Date(file.createdAt),
                // Ensure all required fields are present with safe defaults
                id: file.id || `file-${Date.now()}-${Math.random()}`,
                filename: file.filename || 'Unknown File',
                fileType: file.fileType || 'unknown',
                fileSize: typeof file.fileSize === 'number' ? file.fileSize : 0,
                storagePath: file.storagePath || '',
                isProcessed: file.isProcessed !== undefined ? file.isProcessed : false,
                isDeleted: file.isDeleted !== undefined ? file.isDeleted : false,
                metadata: file.metadata || {},
              }));
              console.log(`[FileStore] Successfully processed ${processedFiles.length} files during rehydration`);
            } else {
              console.log('[FileStore] No valid files array found, initializing empty');
              processedFiles = [];
            }
            
            // Ensure selectedFileIds is an array
            const processedSelectedIds = Array.isArray(state.selectedFileIds) ? state.selectedFileIds : [];
            
            // Update the state directly during rehydration
            state.files = processedFiles;
            state.selectedFileIds = processedSelectedIds;
            state._hasHydrated = true;
            state._rehydrationError = null;
            
            console.log('[FileStore] Rehydration completed successfully');
            
          } catch (fixError) {
            console.error('[FileStore] Error processing files during rehydration:', fixError);
            // On processing error, reset to safe empty state but mark as hydrated
            state.files = [];
            state.selectedFileIds = [];
            state._hasHydrated = true;
            state._rehydrationError = `File processing failed: ${fixError instanceof Error ? fixError.message : 'Unknown error'}`;
          }
        };
      }
    }
  )
) as unknown as {
    (): FileStore;
    <U>(selector: (state: FileStore) => U, equalityFn?: (a: U, b: U) => boolean): U;
    getState: () => FileStore;
    setState: (partial: FileStore | Partial<FileStore> | ((state: FileStore) => FileStore | Partial<FileStore>), replace?: boolean | undefined) => void;
    subscribe: (listener: (state: FileStore, prevState: FileStore) => void) => () => void;
    destroy: () => void;
};

// Ensure hydration flag is set after initialization
setTimeout(() => {
  const currentState = useFileStore.getState();
  if (!currentState._hasHydrated) {
    console.log('[FileStore] Setting hydrated flag for stores without persisted data');
    useFileStore.setState({ _hasHydrated: true, _rehydrationError: null });
  }
}, 100);

export default useFileStore; 