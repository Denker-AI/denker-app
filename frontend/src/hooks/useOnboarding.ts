import { useState, useEffect } from 'react';
import { useAuth } from '../auth/AuthContext';
import useConversationStore from '../store/conversationStore';

interface OnboardingState {
  shouldShowOnboarding: boolean;
  isOnboardingOpen: boolean;
  isFirstTimeUser: boolean;
}

export const useOnboarding = () => {
  const { isAuthenticated } = useAuth();
  const conversationStore = useConversationStore();
  
  const [onboardingState, setOnboardingState] = useState<OnboardingState>({
    shouldShowOnboarding: false,
    isOnboardingOpen: false,
    isFirstTimeUser: false
  });

  useEffect(() => {
    if (!isAuthenticated) {
      setOnboardingState({
        shouldShowOnboarding: false,
        isOnboardingOpen: false,
        isFirstTimeUser: false
      });
      return;
    }

    // Add a small delay to ensure app is fully initialized
    const timer = setTimeout(() => {
      // Check if user is first-time (no conversations)
      const isFirstTimeUser = conversationStore.conversations.length === 0;
    
    // Check localStorage flags
    const hasCompletedOnboarding = localStorage.getItem('denker_onboarding_completed') === 'true';
    const hasSkippedOnboarding = localStorage.getItem('denker_onboarding_skipped') === 'true';
    
    // Check if user manually requested to see onboarding again
    const requestedOnboarding = localStorage.getItem('denker_show_onboarding_requested') === 'true';
    
    // Determine if we should show onboarding
    const shouldShow = isFirstTimeUser && !hasCompletedOnboarding && !hasSkippedOnboarding;
    const shouldShowRequested = requestedOnboarding && !hasCompletedOnboarding;
    
    console.log('[useOnboarding] Evaluation:', {
      isFirstTimeUser,
      hasCompletedOnboarding,
      hasSkippedOnboarding,
      requestedOnboarding,
      shouldShow: shouldShow || shouldShowRequested
    });

      setOnboardingState({
        shouldShowOnboarding: shouldShow || shouldShowRequested,
        isOnboardingOpen: shouldShow || shouldShowRequested,
        isFirstTimeUser
      });

      // Clear the manual request flag if it was set
      if (requestedOnboarding) {
        localStorage.removeItem('denker_show_onboarding_requested');
      }
    }, 1000); // 1 second delay

    return () => clearTimeout(timer);
  }, [isAuthenticated, conversationStore.conversations.length]);

  const openOnboarding = () => {
    setOnboardingState(prev => ({
      ...prev,
      isOnboardingOpen: true
    }));
  };

  const closeOnboarding = () => {
    setOnboardingState(prev => ({
      ...prev,
      isOnboardingOpen: false,
      shouldShowOnboarding: false
    }));
  };

  const skipOnboarding = () => {
    closeOnboarding();
  };

  const requestOnboardingReplay = () => {
    localStorage.setItem('denker_show_onboarding_requested', 'true');
    // This will trigger a re-evaluation on next app load/login
  };

  const resetOnboardingState = () => {
    localStorage.removeItem('denker_onboarding_completed');
    localStorage.removeItem('denker_onboarding_skipped');
    localStorage.removeItem('denker_onboarding_completed_date');
    localStorage.removeItem('denker_onboarding_skipped_date');
    localStorage.removeItem('denker_show_onboarding_requested');
  };

  return {
    ...onboardingState,
    openOnboarding,
    closeOnboarding,
    skipOnboarding,
    requestOnboardingReplay,
    resetOnboardingState
  };
}; 