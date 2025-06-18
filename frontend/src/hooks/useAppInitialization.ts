import { useState, useEffect } from 'react';
import { useAuth } from '../auth/AuthContext';
import useFileStore from '../store/fileStore';
import useConversationStore from '../store/conversationStore';

interface AppInitializationState {
  isInitialized: boolean;
  isLoading: boolean;
  initializationError: string | null;
  loadingMessage: string;
  loadingProgress: number;
  isFirstTimeUser: boolean;
}

/**
 * Hook to coordinate app initialization and prevent flashing between loading states
 * Waits for all critical stores to be hydrated before showing the main app
 * Detects first-time users and shows extended onboarding
 */
export const useAppInitialization = (): AppInitializationState => {
  const { isAuthenticated, isLoading: authLoading, error: authError, isFromLogout } = useAuth();
  const fileStore = useFileStore();
  const conversationStore = useConversationStore();
  
  const [initializationState, setInitializationState] = useState<AppInitializationState>({
    isInitialized: false,
    isLoading: true,
    initializationError: null,
    loadingMessage: 'Starting up...',
    loadingProgress: 0,
    isFirstTimeUser: false
  });

  const [loadingStartTime] = useState<number>(Date.now());
  const [minLoadingTimeReached, setMinLoadingTimeReached] = useState<boolean>(false);
  const [hasBeenAuthenticated, setHasBeenAuthenticated] = useState<boolean>(false);

  // Detect if user is first-time based on conversation history
  const isFirstTimeUser = isAuthenticated && conversationStore.conversations.length === 0;

  // Track if user has been authenticated during this session
  useEffect(() => {
    if (isAuthenticated && !hasBeenAuthenticated) {
      setHasBeenAuthenticated(true);
    }
  }, [isAuthenticated, hasBeenAuthenticated]);

  // Set minimum loading time based on user type and context
  // Skip minimum loading time for re-login scenarios  
  const shouldSkipMinLoadingTime = isFromLogout && hasBeenAuthenticated;
  const minLoadingDuration = shouldSkipMinLoadingTime ? 0 : (isFirstTimeUser ? 10000 : 3000); // Keep original times: 10s for first-time, 3s for returning users

  useEffect(() => {
    const checkInitialization = () => {
      let progress = 0;
      let message = 'Waking up Denker...';
      let error: string | null = null;

      // Special handling for logout scenarios
      if (isFromLogout && !isAuthenticated && !authLoading) {
        setInitializationState({
          isInitialized: true, // Consider logout immediately initialized
          isLoading: false,
          initializationError: null,
          loadingMessage: 'Logged out successfully',
          loadingProgress: 100,
          isFirstTimeUser: false
        });
        return;
      }

      // Check authentication (30% of progress)
      if (authError) {
        error = authError;
        // Make auth error messages more user-friendly
        if (authError.includes('email_not_verified') || authError.includes('verify your email')) {
          message = 'Please check your email and verify your account';
        } else if (authError.includes('Network')) {
          message = 'Network issue - please check your connection';
        } else {
          message = 'Authentication issue - please try signing in again';
        }
        progress = 15; // Some progress even on error
      } else if (isAuthenticated) {
        progress += 30;
        if (isFirstTimeUser) {
          message = 'Welcome to Denker! Setting up your AI assistant...';
        } else {
          message = shouldSkipMinLoadingTime 
            ? 'Welcome back!' 
            : 'Welcome back! Powering up your AI assistant...';
        }
      } else if (!authLoading) {
        progress += 15; // Partial progress if auth is done but not authenticated
        message = isFromLogout ? 'Logged out successfully' : 'Getting ready for sign-in...';
      }

      // Check file store hydration (35% of progress)
      if (fileStore._hasHydrated) {
        progress += 35;
        if (fileStore._rehydrationError) {
          console.warn('[useAppInitialization] File store rehydration error:', fileStore._rehydrationError);
          // Don't fail initialization for file store errors, just log them
        }
        
        if (progress >= 65) {
          message = shouldSkipMinLoadingTime
            ? 'Ready!'
            : isFirstTimeUser 
              ? 'Setting up your intelligent workspace...' 
              : 'Loading your intelligent tools...';
        } else if (progress >= 45) {
          message = shouldSkipMinLoadingTime
            ? 'Almost ready...'
            : isFirstTimeUser 
              ? 'Preparing your personalized AI experience...' 
              : 'Preparing your workspace...';
        }
      }

      // Check conversation store (35% of progress)
      // Conversation store doesn't have explicit hydration flag, so we assume it's ready
      // if auth is complete (authenticated or has error)
      if (isAuthenticated || authError || !authLoading) {
        progress += 35;
        
        if (progress >= 95) {
          message = shouldSkipMinLoadingTime
            ? 'Welcome back!'
            : isFirstTimeUser 
              ? 'Almost ready! Get excited for maximum productivity!' 
              : 'Welcome back to Denker!';
        } else if (progress >= 85) {
          message = shouldSkipMinLoadingTime
            ? 'Ready!'
            : isFirstTimeUser 
              ? 'Finalizing your AI assistant setup...' 
              : 'Getting everything ready...';
        } else if (progress >= 70) {
          message = shouldSkipMinLoadingTime
            ? 'Loading...'
            : isFirstTimeUser 
              ? 'Preparing your conversation experience...' 
              : 'Loading conversation history...';
        }
      }

      // Consider initialization complete when:
      // 1. Auth state is determined (authenticated, has error, OR auth check is complete)
      // 2. File store is hydrated (or failed gracefully)  
      // 3. Minimum loading time has passed (or can be skipped for re-login)
      const authComplete: boolean = isAuthenticated || authError !== null || !authLoading;
      const technicallyReady: boolean = authComplete && fileStore._hasHydrated;
      const isInitialized: boolean = technicallyReady && (minLoadingTimeReached || shouldSkipMinLoadingTime);
      


      setInitializationState({
        isInitialized,
        isLoading: !isInitialized,
        initializationError: error,
        loadingMessage: message,
        loadingProgress: Math.min(progress, 100),
        isFirstTimeUser
      });
    };

    checkInitialization();
  }, [
    authLoading, 
    isAuthenticated, 
    authError, 
    isFromLogout,
    fileStore._hasHydrated, 
    fileStore._rehydrationError,
    minLoadingTimeReached,
    isFirstTimeUser,
    shouldSkipMinLoadingTime
  ]);

  // Timer to enforce minimum loading duration (unless skipping)
  useEffect(() => {
    if (minLoadingDuration > 0) {
      const timer = setTimeout(() => {
        setMinLoadingTimeReached(true);
      }, minLoadingDuration);

      return () => clearTimeout(timer);
    } else {
      // If no minimum loading time required, mark as reached immediately
      setMinLoadingTimeReached(true);
    }
  }, [minLoadingDuration]);

  // Failsafe timeout to prevent infinite loading
  useEffect(() => {
    const failsafeTimeout = setTimeout(() => {
      if (initializationState.isLoading) {
        console.warn('[useAppInitialization] Failsafe timeout reached, forcing initialization complete');
        setInitializationState(prev => ({
          ...prev,
          isInitialized: true,
          isLoading: false,
          initializationError: prev.initializationError || 'Initialization took longer than expected'
        }));
      }
    }, 20000); // 20 seconds failsafe

    return () => clearTimeout(failsafeTimeout);
  }, [initializationState.isLoading]);

  return initializationState;
};

export default useAppInitialization; 