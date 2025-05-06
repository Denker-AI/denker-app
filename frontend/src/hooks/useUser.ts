import { useState, useCallback, useEffect } from 'react';
import { useAuth0 } from '@auth0/auth0-react';
import useUserStore, { UserProfile, UserSettings } from '../store/userStore';
import { useApi } from '../services/api';

export const useUser = () => {
  const { isAuthenticated, isLoading: isAuthLoading, loginWithRedirect, logout, user: auth0User } = useAuth0();
  const api = useApi();
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Get user state from store
  const {
    profile,
    settings,
    setProfile,
    updateProfile,
    setSettings,
    updateSettings,
    resetState,
  } = useUserStore();
  
  // Load user profile from API when authenticated
  useEffect(() => {
    if (isAuthenticated && auth0User && !profile) {
      loadUserProfile();
    }
  }, [isAuthenticated, auth0User, profile]);
  
  // Load user profile from API
  const loadUserProfile = useCallback(async () => {
    if (!isAuthenticated) return null;
    
    setIsLoading(true);
    setError(null);
    
    try {
      // First, ensure we're logged in with the backend
      await api.login();
      
      // Then get the user profile
      const response = await api.getUserProfile();
      const userData = response.data;
      
      // Transform API response to match our store format
      const userProfile: UserProfile = {
        id: userData.id,
        email: userData.email,
        name: userData.name,
        picture: userData.metadata?.picture || auth0User?.picture,
        metadata: userData.metadata,
      };
      
      setProfile(userProfile);
      
      // Load user settings
      await loadUserSettings();
      
      return userProfile;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to load user profile';
      setError(errorMessage);
      
      // If we have Auth0 user data, create a minimal profile
      if (auth0User) {
        const minimalProfile: UserProfile = {
          id: auth0User.sub || '',
          email: auth0User.email || '',
          name: auth0User.name || '',
          picture: auth0User.picture,
        };
        setProfile(minimalProfile);
        return minimalProfile;
      }
      
      return null;
    } finally {
      setIsLoading(false);
    }
  }, [isAuthenticated, auth0User, api, setProfile]);
  
  // Load user settings from API
  const loadUserSettings = useCallback(async () => {
    if (!isAuthenticated) return null;
    
    setIsLoading(true);
    setError(null);
    
    try {
      const response = await api.getUserSettings();
      const settingsData = response.data;
      
      setSettings(settingsData);
      
      return settingsData;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to load user settings';
      setError(errorMessage);
      return null;
    } finally {
      setIsLoading(false);
    }
  }, [isAuthenticated, api, setSettings]);
  
  // Update user profile
  const updateUserProfile = useCallback(async (updates: Partial<UserProfile>) => {
    if (!isAuthenticated || !profile) {
      setError('User not authenticated');
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
      
      const response = await api.updateUserProfile(allowedUpdates);
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
  }, [isAuthenticated, profile, api, updateProfile]);
  
  // Update user settings
  const updateUserSettings = useCallback(async (updates: Partial<UserSettings>) => {
    if (!isAuthenticated) {
      setError('User not authenticated');
      return null;
    }
    
    setIsLoading(true);
    setError(null);
    
    try {
      // Update local state immediately for better UX
      updateSettings(updates);
      
      // Then send to API
      const response = await api.updateUserSettings({
        ...settings,
        ...updates,
      });
      
      return response.data;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to update user settings';
      setError(errorMessage);
      return null;
    } finally {
      setIsLoading(false);
    }
  }, [isAuthenticated, settings, api, updateSettings]);
  
  // Handle logout
  const handleLogout = useCallback(() => {
    resetState();
    logout({ logoutParams: { returnTo: window.location.origin } });
  }, [logout, resetState]);
  
  return {
    isAuthenticated,
    isLoading: isLoading || isAuthLoading,
    error,
    profile,
    settings,
    
    // Auth actions
    login: loginWithRedirect,
    logout: handleLogout,
    
    // Profile actions
    loadUserProfile,
    updateUserProfile,
    
    // Settings actions
    loadUserSettings,
    updateUserSettings,
  };
};

export default useUser; 