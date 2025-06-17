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
}

export type FileStore = FileStoreState & FileStoreActions;

const useFileStore = create<FileStore>()(
  persist(
    (set, get) => ({
      files: [],
      selectedFileIds: [],
      _hasHydrated: false,
      
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
      }
    }),
    {
      name: 'denker-file-storage',
      storage: createJSONStorage(() => localStorage),
      partialize: (state: FileStore) => ({
        files: state.files,
        selectedFileIds: state.selectedFileIds
      }),
      onRehydrateStorage: (state?: FileStoreState, error?: Error | null): void => {
        if (error) {
          console.error('[FileStore] an error happened during rehydration:', error);
          // Set hydrated flag even on error to prevent infinite waiting
          useFileStore.setState({ _hasHydrated: true });
          return;
        }
        
        if (!state) {
          console.log('[FileStore] No state found in storage, initializing empty state');
          useFileStore.setState({ _hasHydrated: true });
          return;
        }
        
        if (state.files) {
          try {
            const fixedFiles = state.files.map((file: FileItem) => ({
              ...file,
              createdAt: file.createdAt instanceof Date ? file.createdAt : new Date(file.createdAt),
              // Ensure all required fields are present
              id: file.id || `file-${Date.now()}-${Math.random()}`,
              filename: file.filename || 'Unknown File',
              fileType: file.fileType || 'unknown',
              fileSize: file.fileSize || 0,
              storagePath: file.storagePath || '',
              isProcessed: file.isProcessed !== undefined ? file.isProcessed : false,
              isDeleted: file.isDeleted !== undefined ? file.isDeleted : false,
              metadata: file.metadata || {},
            }));
            state.files = fixedFiles;
            console.log(`[FileStore] Fixed ${fixedFiles.length} files during rehydration`);
          } catch (fixError) {
            console.error('[FileStore] Error fixing files during rehydration:', fixError);
            // Reset to empty array if fixing fails
            state.files = [];
          }
        } else {
          state.files = [];
        }
        
        console.log('File store rehydrated from storage');
        
        // Use setTimeout to ensure state update happens after the current execution
        // but only if not already hydrated to prevent duplicate setState calls
        const currentState = useFileStore.getState();
        if (!currentState._hasHydrated) {
          setTimeout(() => {
            useFileStore.setState({ _hasHydrated: true });
          }, 0);
        }
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

export default useFileStore; 