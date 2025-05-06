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
      storage: createJSONStorage(() => localStorage), // use localStorage by default
      partialize: (state) => ({
        // Only store user data and settings, not loading states
        profile: state.profile,
        settings: state.settings
      })
    }
  )
);

export default useUserStore; 