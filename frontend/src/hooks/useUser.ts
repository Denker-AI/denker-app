import { useState, useCallback } from 'react';
// import { useAuth0 } from '@auth0/auth0-react'; // REMOVE Auth0 dependency
import useUserStore, { UserProfile, UserSettings } from '../store/userStore';
// REMOVE useApi import
// import { useApi } from '../services/api';
import api from '../services/api'; // IMPORT default axios instance

export const useUser = () => {
  // REMOVE Auth0 related state/hooks
  // const { isAuthenticated, isLoading: isAuthLoading, loginWithRedirect, logout, user: auth0User } = useAuth0();
  // const api = useApi(); // REMOVED
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Zustand store selectors and actions
  const { profile, settings, setProfile, setSettings, updateProfile, updateSettings, resetState } = useUserStore();
  
  // Load user profile from API
  const loadUserProfile = useCallback(async () => {
    // REMOVED Auth0 check
    console.log('🔍 Starting loadUserProfile.');
    
    setIsLoading(true);
    setError(null);
    
    try {
      // REMOVED backend login call (should be handled by auth flow)
      // console.log('🌐 Attempting backend login');
      // const loginResponse = await api.login(); 
      // console.log('✅ Backend login successful:', loginResponse);
      
      // Fetch the user profile using the directly imported api instance
      console.log('👤 Fetching user profile');
      const response = await api.get('/users/profile'); // USE api.get directly
      const userData = response.data;
      
      console.log('✨ Loaded user profile from API:', userData);
      
      // Transform API response to match our store format
      const userProfile: UserProfile = {
        id: userData.id, // Use ID from backend
        email: userData.email,
        name: userData.name,
        picture: userData.metadata?.picture, // Get picture from metadata if available
        metadata: userData.metadata,
      };
      
      console.log('💾 Setting user profile:', userProfile);
      setProfile(userProfile);
      
      // Load user settings
      console.log('⚙️ Loading user settings');
      await loadUserSettings();
      
      console.log('🎉 User profile and settings loaded successfully');
      return userProfile;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to load user profile';
      console.error('❌ Error loading user profile:', errorMessage, err);
      setError(errorMessage);
      return null;
    } finally {
      setIsLoading(false);
    }
  }, [setProfile, updateProfile]); // REMOVED api, auth0User, isAuthenticated dependencies
  
  // Load user settings from API
  const loadUserSettings = useCallback(async () => {
    // REMOVED Auth0 check
    setIsLoading(true); // Keep loading state management if needed
    try {
      const response = await api.get('/users/settings'); // USE api.get directly
      console.log('💾 Setting user settings:', response.data);
      setSettings(response.data);
      return response.data;
    } catch (err) {
      console.error('Error loading user settings:', err);
      // Don't necessarily set a global error here, maybe handle locally
      return null;
    } finally {
      setIsLoading(false); // Keep loading state management if needed
    }
  }, [setSettings]); // REMOVED api, isAuthenticated dependencies
  
  // Update user profile
  const updateUserProfile = useCallback(async (updates: Partial<UserProfile>) => {
    // REMOVED Auth0 check
    if (!profile) { // Check if profile exists locally
      setError('User profile not loaded');
      return null;
    }
    
    setIsLoading(true);
    setError(null);
    
    try {
      // Only send allowed fields to API
      const allowedUpdates = {
        name: updates.name,
        metadata: updates.metadata,
      };
      
      // User profile changes (like name) are stored in your application's database,
      // not in Auth0. This ensures the changes persist across sessions and devices.
      // The data is sent to the backend API which stores it in the database.
      const response = await api.put('/users/profile', allowedUpdates); // USE api.put directly
      const updatedData = response.data;
      
      // Update local state
      updateProfile({
        name: updatedData.name,
        metadata: updatedData.metadata,
      });
      
      return updatedData;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to update user profile';
      setError(errorMessage);
      
      // Still update local state for better UX
      updateProfile(updates);
      
      return null;
    } finally {
      setIsLoading(false);
    }
  }, [profile, api, updateProfile]); // Keep api dependency? No, interceptor handles it.
  
  // Update user settings
  const updateUserSettings = useCallback(async (updates: Partial<UserSettings>) => {
    // REMOVED Auth0 check
    setIsLoading(true);
    setError(null);
    try {
      const response = await api.put('/users/settings', updates); // USE api.put directly
      updateSettings(response.data); // Update store with response
      return response.data;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to update settings';
      setError(errorMessage);
      // Optionally revert or update locally despite error
      return null;
    } finally {
      setIsLoading(false);
    }
  }, [updateSettings]); // REMOVED api, isAuthenticated dependencies
  
  // Return the state and functions (remove Auth0 specific ones)
  return {
    profile,
    settings,
    isLoading,
    error,
    loadUserProfile,
    updateUserProfile,
    loadUserSettings,
    updateUserSettings,
    resetState, // Keep reset state from store
    // REMOVED: loginWithRedirect, logout
  };
};

export default useUser; 