import { create } from 'zustand';
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

interface FileStore {
  files: FileItem[];
  selectedFileIds: string[];
  
  // Actions
  setFiles: (files: FileItem[]) => void;
  addFile: (file: FileItem) => void;
  updateFile: (id: string, updates: Partial<FileItem>) => void;
  deleteFile: (id: string) => void;
  
  // Selection actions
  selectFile: (id: string) => void;
  deselectFile: (id: string) => void;
  toggleFileSelection: (id: string) => void;
  clearSelection: () => void;
  
  // Helpers
  getSelectedFiles: () => FileItem[];
}

const useFileStore = create<FileStore>()(
  persist(
    (set, get) => ({
      files: [],
      selectedFileIds: [],
      
      setFiles: (files) => set({ files }),
      
      addFile: (file) => set((state) => ({
        files: [...state.files, file]
      })),
      
      updateFile: (id, updates) => set((state) => ({
        files: state.files.map((file) =>
          file.id === id ? { ...file, ...updates } : file
        )
      })),
      
      deleteFile: (id) => set((state) => ({
        files: state.files.filter((file) => file.id !== id),
        selectedFileIds: state.selectedFileIds.filter((fileId) => fileId !== id)
      })),
      
      selectFile: (id) => set((state) => ({
        selectedFileIds: [...state.selectedFileIds, id]
      })),
      
      deselectFile: (id) => set((state) => ({
        selectedFileIds: state.selectedFileIds.filter((fileId) => fileId !== id)
      })),
      
      toggleFileSelection: (id) => set((state) => ({
        selectedFileIds: state.selectedFileIds.includes(id)
          ? state.selectedFileIds.filter((fileId) => fileId !== id)
          : [...state.selectedFileIds, id]
      })),
      
      clearSelection: () => set({ selectedFileIds: [] }),
      
      getSelectedFiles: () => {
        const state = get();
        return state.files.filter((file) => state.selectedFileIds.includes(file.id));
      }
    }),
    {
      name: 'denker-file-storage', // unique name for localStorage key
      storage: createJSONStorage(() => localStorage), // use localStorage by default
      partialize: (state) => ({
        // Only store files and selection, not loading states
        files: state.files,
        selectedFileIds: state.selectedFileIds
      }),
      // Handle date serialization/deserialization
      onRehydrateStorage: () => (state) => {
        // Convert date strings back to Date objects after rehydration
        if (state && state.files) {
          const fixedFiles = state.files.map(file => ({
            ...file,
            createdAt: new Date(file.createdAt)
          }));
          state.files = fixedFiles;
        }
        console.log('File store rehydrated from storage');
      }
    }
  )
);

export default useFileStore; 