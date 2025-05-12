import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';

export interface UserSettings {
  theme: 'light' | 'dark' | 'system';
  fontSize: 'small' | 'medium' | 'large';
  notifications: boolean;
  autoSave: boolean;
  [key: string]: any;
}

export interface UserProfile {
  id: string;
  email: string;
  name: string;
  picture?: string;
  metadata?: Record<string, any>;
}

interface UserState {
  profile: UserProfile | null;
  settings: UserSettings;
  isLoading: boolean;
  error: string | null;
  
  // Actions
  setProfile: (profile: UserProfile | null) => void;
  updateProfile: (updates: Partial<UserProfile>) => void;
  setSettings: (settings: UserSettings) => void;
  updateSettings: (updates: Partial<UserSettings>) => void;
  
  // Loading state
  setLoading: (isLoading: boolean) => void;
  setError: (error: string | null) => void;
  
  // Reset
  resetState: () => void;
}

const defaultSettings: UserSettings = {
  theme: 'dark',
  fontSize: 'medium',
  notifications: true,
  autoSave: true,
};

// Helper to safely serialize/deserialize data with version tracking
const createVersionedStorage = () => {
  const STORAGE_VERSION = '1.1';
  const STORAGE_KEY = 'denker-user-storage';
  
  return {
    getItem: () => {
      const data = localStorage.getItem(STORAGE_KEY);
      if (!data) return null;
      
      try {
        const parsed = JSON.parse(data);
        
        // Check if we have a version mismatch
        if (parsed.version !== STORAGE_VERSION) {
          console.log('Storage version mismatch, clearing stored data');
          localStorage.removeItem(STORAGE_KEY);
          return null;
        }
        
        return data;
      } catch (e) {
        console.error('Error parsing stored user data:', e);
        localStorage.removeItem(STORAGE_KEY);
        return null;
      }
    },
    setItem: (key, newValue) => {
      const valueToStore = JSON.parse(newValue);
      
      // Add version info
      valueToStore.version = STORAGE_VERSION;
      
      // Store with version info
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify(valueToStore)
      );
    },
    removeItem: () => localStorage.removeItem(STORAGE_KEY),
  };
};

const useUserStore = create<UserState>()(
  persist(
    (set) => ({
      profile: null,
      settings: defaultSettings,
      isLoading: false,
      error: null,
      
      // Actions
      setProfile: (profile) => set({ profile }),
      
      updateProfile: (updates) => set((state) => ({
        profile: state.profile ? { ...state.profile, ...updates } : null,
      })),
      
      setSettings: (settings) => set({ settings }),
      
      updateSettings: (updates) => set((state) => ({
        settings: { ...state.settings, ...updates },
      })),
      
      // Loading state
      setLoading: (isLoading) => set({ isLoading }),
      setError: (error) => set({ error }),
      
      // Reset
      resetState: () => set({
        profile: null,
        settings: defaultSettings,
        isLoading: false,
        error: null,
      }),
    }),
    {
      name: 'denker-user-storage', // unique name for localStorage key
      storage: createJSONStorage(() => createVersionedStorage()),
      partialize: (state) => ({
        // Only store user data and settings, not loading states
        profile: state.profile,
        settings: state.settings
      })
    }
  )
);

export default useUserStore; 