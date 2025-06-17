import { useEffect, useCallback } from 'react';
import useOnboardingStore from '../store/onboardingStore';

/**
 * Hook to monitor global shortcuts and track their usage for onboarding
 */
export const useShortcutMonitor = () => {
  const { markShortcutUsed } = useOnboardingStore();

  // Handle global shortcut detection
  const handleShortcutUsed = useCallback(() => {
    console.log('[useShortcutMonitor] Global shortcut detected (Cmd+Shift+D)');
    markShortcutUsed();
  }, [markShortcutUsed]);

  useEffect(() => {
    // Listen for the shortcut event from Electron main process
    const handleShortcutEvent = () => {
      handleShortcutUsed();
    };

    // Check if we're in an Electron environment
    if (window.electron) {
      // Listen for shortcut events from the main process
      window.electron.ipcRenderer?.on?.('global-shortcut-triggered', handleShortcutEvent);
      
      // Cleanup listener on unmount
      return () => {
        window.electron.ipcRenderer?.removeListener?.('global-shortcut-triggered', handleShortcutEvent);
      };
    }

    // For web environments, we can't listen to global shortcuts, 
    // but we can detect when the app gains focus after being minimized
    const handleFocus = () => {
      // This is a proxy for shortcut usage in web environments
      // In a real Electron app, the global shortcut would be handled by the main process
      console.log('[useShortcutMonitor] App gained focus - potential shortcut usage');
      handleShortcutUsed();
    };

    window.addEventListener('focus', handleFocus);
    
    return () => {
      window.removeListener('focus', handleFocus);
    };
  }, [handleShortcutUsed]);

  return {
    triggerShortcutDetection: handleShortcutUsed
  };
}; 