import { useState, useCallback, useEffect } from 'react';
import { useAuth0 } from '@auth0/auth0-react';
import useUserStore, { UserProfile, UserSettings } from '../store/userStore';
import { useApi } from '../services/api';

export const useUser = () => {
  const { isAuthenticated, isLoading: isAuthLoading, loginWithRedirect, logout, user: auth0User, getAccessTokenSilently } = useAuth0();
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
  
  // Clear user profile when logging in with a different account
  useEffect(() => {
    if (auth0User && profile && auth0User.sub !== profile.id) {
      console.log('Different user detected, clearing cached profile');
      resetState();
    }
  }, [auth0User, profile, resetState]);
  
  // Load user profile from API when authenticated
  useEffect(() => {
    if (isAuthenticated && auth0User && (!profile || auth0User.sub !== profile.id)) {
      console.log('Loading user profile for', auth0User.email);
      loadUserProfile();
    }
  }, [isAuthenticated, auth0User, profile]);
  
  // Load user profile from API
  const loadUserProfile = useCallback(async () => {
    if (!isAuthenticated || !auth0User) return null;
    
    setIsLoading(true);
    setError(null);
    
    try {
      // First, ensure we're logged in with the backend
      await api.login();
      
      // Then get the user profile
      const response = await api.getUserProfile();
      const userData = response.data;
      
      console.log('Loaded user profile from API:', userData);
      
      // Transform API response to match our store format
      const userProfile: UserProfile = {
        id: userData.id || auth0User.sub,
        email: userData.email || auth0User.email,
        name: userData.name || auth0User.name,
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
      console.error('Error loading user profile:', errorMessage);
      
      // If we have Auth0 user data, create a minimal profile
      if (auth0User) {
        console.log('Creating minimal profile from Auth0 user:', auth0User);
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
      
      // User profile changes (like name) are stored in your application's database,
      // not in Auth0. This ensures the changes persist across sessions and devices.
      // The data is sent to the backend API which stores it in the database.
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
    console.log('Logging out and clearing user data');
    resetState();
    
    // Clear any cached Auth0 data from localStorage
    const keysToRemove = [];
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key && (key.startsWith('auth0') || key.includes('auth0') || key.includes('denker'))) {
        keysToRemove.push(key);
      }
    }
    
    keysToRemove.forEach(key => {
      console.log('Removing cached key:', key);
      localStorage.removeItem(key);
    });
    
    // Log out from Auth0
    logout({ logoutParams: { returnTo: window.location.origin } });
  }, [logout, resetState]);
  
  // Handle custom login (clears any existing data first)
  const handleLogin = useCallback(() => {
    console.log('Initiating login, clearing any existing data');
    resetState();
    
    // Clear any cached Auth0 data from localStorage
    const keysToRemove = [];
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key && (key.startsWith('auth0') || key.includes('auth0') || key.includes('denker'))) {
        keysToRemove.push(key);
      }
    }
    
    keysToRemove.forEach(key => localStorage.removeItem(key));
    
    // Log in with Auth0
    loginWithRedirect();
  }, [loginWithRedirect, resetState]);
  
  return {
    isAuthenticated,
    isLoading: isLoading || isAuthLoading,
    error,
    profile,
    settings,
    
    // Auth actions
    login: handleLogin,
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