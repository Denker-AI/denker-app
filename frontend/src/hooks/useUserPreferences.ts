import { useState, useEffect, useMemo, useCallback } from 'react';
import { useAuth } from '../auth/AuthContext';

// Local storage key for user preferences
const USER_PREFERENCES_KEY = 'denker_user_preferences';

export interface UserPreferences {
  displayName?: string;
  avatarUrl?: string;
}

export const useUserPreferences = () => {
  const { user } = useAuth();
  const [userPreferences, setUserPreferences] = useState<UserPreferences>({});
  
  // Load user preferences from localStorage
  const loadUserPreferences = (): UserPreferences => {
    if (!user?.sub) return {};
    
    try {
      const stored = localStorage.getItem(`${USER_PREFERENCES_KEY}_${user.sub}`);
      return stored ? JSON.parse(stored) : {};
    } catch (error) {
      console.error('Error loading user preferences:', error);
      return {};
    }
  };
  
  // Save user preferences to localStorage
  const saveUserPreferences = useCallback((preferences: UserPreferences) => {
    if (!user?.sub) return;
    
    try {
      localStorage.setItem(`${USER_PREFERENCES_KEY}_${user.sub}`, JSON.stringify(preferences));
      setUserPreferences(preferences);
    } catch (error) {
      console.error('Error saving user preferences:', error);
    }
  }, [user?.sub]);
  
  // Get effective display name (custom or Auth0)
  const getDisplayName = useMemo((): string => {
    return userPreferences.displayName || user?.name || '';
  }, [userPreferences.displayName, user?.name]);
  
  // Get effective avatar URL (custom or Auth0)
  const getAvatarUrl = useMemo((): string => {
    return userPreferences.avatarUrl || user?.picture || '';
  }, [userPreferences.avatarUrl, user?.picture]);
  
  // Check if using custom display name
  const isUsingCustomDisplayName = useMemo((): boolean => {
    return !!userPreferences.displayName && userPreferences.displayName !== user?.name;
  }, [userPreferences.displayName, user?.name]);
  
  // Check if using custom avatar
  const isUsingCustomAvatar = useMemo((): boolean => {
    return !!userPreferences.avatarUrl && userPreferences.avatarUrl !== user?.picture;
  }, [userPreferences.avatarUrl, user?.picture]);
  
  // Load preferences when user changes
  useEffect(() => {
    if (user?.sub) {
      const preferences = loadUserPreferences();
      setUserPreferences(preferences);
    } else {
      setUserPreferences({});
    }
  }, [user?.sub]); // Remove the function from dependencies to prevent re-creation loops
  
  return {
    userPreferences,
    getDisplayName,
    getAvatarUrl,
    isUsingCustomDisplayName,
    isUsingCustomAvatar,
    saveUserPreferences,
    loadUserPreferences,
    
    // Original Auth0 values for reference
    originalName: user?.name,
    originalPicture: user?.picture,
    email: user?.email,
    userId: user?.sub,
  };
};

export default useUserPreferences; 