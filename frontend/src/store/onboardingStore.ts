import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';

interface OnboardingState {
  hasCompletedOnboarding: boolean;
  shouldShowOnboarding: boolean;
  onboardingStep: number;
  onboardingData: {
    hasUsedShortcut: boolean;
    hasOpenedMenu: boolean;
    hasVisitedSettings: boolean;
    hasViewedProfile: boolean;
    hasSeenFeedback: boolean;
  };
  
  // Actions
  setHasCompletedOnboarding: (completed: boolean) => void;
  setShouldShowOnboarding: (show: boolean) => void;
  setOnboardingStep: (step: number) => void;
  markShortcutUsed: () => void;
  markMenuOpened: () => void;
  markSettingsVisited: () => void;
  markProfileViewed: () => void;
  markFeedbackSeen: () => void;
  resetOnboarding: () => void;
  completeOnboarding: () => void;
}

const useOnboardingStore = create<OnboardingState>()(
  persist(
    (set, get) => ({
      hasCompletedOnboarding: false,
      shouldShowOnboarding: false,
      onboardingStep: 0,
      onboardingData: {
        hasUsedShortcut: false,
        hasOpenedMenu: false,
        hasVisitedSettings: false,
        hasViewedProfile: false,
        hasSeenFeedback: false,
      },
      
      setHasCompletedOnboarding: (completed: boolean) => 
        set({ hasCompletedOnboarding: completed }),
      
      setShouldShowOnboarding: (show: boolean) => 
        set({ shouldShowOnboarding: show }),
      
      setOnboardingStep: (step: number) => 
        set({ onboardingStep: step }),
      
      markShortcutUsed: () =>
        set((state) => ({
          onboardingData: { ...state.onboardingData, hasUsedShortcut: true }
        })),
      
      markMenuOpened: () =>
        set((state) => ({
          onboardingData: { ...state.onboardingData, hasOpenedMenu: true }
        })),
      
      markSettingsVisited: () =>
        set((state) => ({
          onboardingData: { ...state.onboardingData, hasVisitedSettings: true }
        })),
      
      markProfileViewed: () =>
        set((state) => ({
          onboardingData: { ...state.onboardingData, hasViewedProfile: true }
        })),
      
      markFeedbackSeen: () =>
        set((state) => ({
          onboardingData: { ...state.onboardingData, hasSeenFeedback: true }
        })),
      
      resetOnboarding: () =>
        set({
          hasCompletedOnboarding: false,
          shouldShowOnboarding: false,
          onboardingStep: 0,
          onboardingData: {
            hasUsedShortcut: false,
            hasOpenedMenu: false,
            hasVisitedSettings: false,
            hasViewedProfile: false,
            hasSeenFeedback: false,
          },
        }),
      
      completeOnboarding: () =>
        set({
          hasCompletedOnboarding: true,
          shouldShowOnboarding: false,
          onboardingStep: 0,
        }),
    }),
    {
      name: 'denker-onboarding-storage',
      storage: createJSONStorage(() => localStorage),
    }
  )
);

export default useOnboardingStore; 