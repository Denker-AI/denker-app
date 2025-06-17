import React, { createContext, useState, useEffect, useContext, ReactNode, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { CircularProgress } from '@mui/material';
import { api } from '../services/api';
import { LoadingScreen } from '../components/Common';
import { clearUserInfoCache, getUserInfoCached } from '../utils/user-info-cache';
import { getCachedAccessToken, clearTokenCache } from '../utils/token-cache';

// Define the shape of the user info (adjust based on claims)
interface UserInfo {
  name?: string;
  nickname?: string;
  picture?: string;
  email?: string;
  email_verified?: boolean;
  sub?: string;
}

// Define the shape of the context data
interface AuthContextType {
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  user: UserInfo | null; // Add user state
  isFromLogout: boolean; // Add logout tracking
  showOnboarding: boolean; // Add onboarding modal state
  login: () => void;
  logout: () => void;
  getAccessToken: () => Promise<string | null>;
  restartCoordinator: () => Promise<void>; // Add restart function
  hideOnboarding: () => void; // Add function to hide onboarding
  showOnboardingModal: () => void; // Add function to show onboarding on demand
  // Optional: Add a function to refetch user info if needed
  // refreshUserInfo: () => Promise<void>; 
}

// Create the context with a default undefined value to ensure it's used within a provider
export const AuthContext = createContext<AuthContextType | undefined>(undefined);

// Define the props for the provider component
interface AuthProviderProps {
  children: ReactNode;
}

// Create the provider component
export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  // Check if current path is subwindow using window.location
  const isSubWindow = window.location.hash === '#/subwindow';
  
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(!isSubWindow); // Skip loading for subwindow
  const [error, setError] = useState<string | null>(null);
  const [user, setUser] = useState<UserInfo | null>(null); // Add user state
  const [backendReady, setBackendReady] = useState<boolean>(false); // Add backend readiness state
  const [backendError, setBackendError] = useState<string | null>(null); // Add backend error state
  const [isFromLogout, setIsFromLogout] = useState<boolean>(false); // Add logout tracking
  const [showOnboarding, setShowOnboarding] = useState<boolean>(false); // Add onboarding modal state
  const authSuccessHandledRef = useRef<boolean>(false); // Track auth success handling

  // Function to fetch user info via IPC (now uses cached version to prevent Auth0 rate limits)
  const fetchUserInfo = useCallback(async () => {
    console.log('[AuthContext] Fetching user info via cached method...');
    try {
      const userInfo = await getUserInfoCached(); // Use cached version to prevent Auth0 calls
      if (userInfo) {
        console.log('[AuthContext] User info received from cache:', userInfo);
        setUser(userInfo);
        return userInfo; // Return the user info for immediate use
      } else {
        console.log('[AuthContext] No user info returned from cache.');
        setUser(null);
        return null;
      }
    } catch (e) {
      console.error('[AuthContext] Error fetching user info from cache:', e);
      setUser(null); // Clear user info on error
      return null;
    }
  }, []);

  const getAccessToken = useCallback(async (): Promise<string | null> => {
    console.log('[AuthContext] Requesting token via cached token system');
    try {
      const token = await getCachedAccessToken();
      if (!token) {
        console.log('[AuthContext] No access token returned from cached system.');
        // If no token, ensure we are marked as not authenticated
        if (isAuthenticated) {
          setIsAuthenticated(false);
        }
        return null;
      }
      console.log('[AuthContext] Received access token from cached system.');
      return token;
    } catch (e) {
      console.error('[AuthContext] Error getting access token:', e);
      setError('Failed to retrieve access token.');
      if (isAuthenticated) {
        setIsAuthenticated(false);
      }
      return null;
    }
  }, [isAuthenticated]);

  // Combined function to fetch user info and post to local backend
  const postLocalLogin = useCallback(async (userInfo: UserInfo) => {
    console.log('[AuthContext] Posting user info to local backend...');
    try {
      const token = await getAccessToken();
      if (!token) {
        console.error('[AuthContext] No token available for postLocalLogin');
        return;
      }
      
      const result = await api.postLocalLogin({
        user_id: userInfo.sub,
        token: token,
      });
      
      console.log('[AuthContext] Successfully posted user info to local backend:', result);
      
      // Log the authentication scenario for debugging
      if (result.auth_scenario) {
        console.log(`[AuthContext] Auth scenario: ${result.auth_scenario}, Coordinator action: ${result.coordinator_action}`);
      }
      
      return result;
    } catch (err) {
      console.error('[AuthContext] Failed to post user info to local backend:', err);
      throw err;
    }
  }, [getAccessToken]);

  // Function to check if this is a first-time login
  const checkFirstTimeLogin = useCallback(async (userInfo: UserInfo) => {
    const hasCompletedOnboarding = localStorage.getItem('denker_onboarding_completed');
    
    // Show onboarding if user hasn't completed it before
    if (!hasCompletedOnboarding && userInfo.sub) {
      console.log('[AuthContext] First-time login detected, showing onboarding');
      setShowOnboarding(true);
    }
  }, []);

  // Combined function for auth success flow
  const handleAuthSuccess = useCallback(async () => {
    console.log('[AuthContext] Handling authentication success...');
    
    // Prevent duplicate auth success processing
    if (isAuthenticated) {
      console.log('[AuthContext] Already authenticated, skipping duplicate handleAuthSuccess');
      return;
    }
    
    setError(null);
    setIsFromLogout(false); // Reset logout flag on successful login
    
    // Fetch user info and validate user exists
    const userInfo = await fetchUserInfo();
    if (!userInfo) {
      console.error('[AuthContext] User info could not be fetched - user may not exist or token may be invalid');
      // Clear caches since the user doesn't exist
      clearTokenCache();
      clearUserInfoCache();
      setError('User account not found. Please log in again.');
      setIsAuthenticated(false);
      setUser(null);
      return;
    }
    
    // Check if email verification is required
    if (userInfo.email_verified === false) {
      console.log('[AuthContext] Email not verified, redirecting to verification page');
      clearTokenCache();
      clearUserInfoCache();
      setError('Please verify your email address to continue.');
      setIsAuthenticated(false);
      setUser(null);
      // Redirect to email verification page
      window.location.href = '/email-verification';
      return;
    }
    
    // Only set authenticated if we successfully got user info and email is verified
    setIsAuthenticated(true);
    setIsFromLogout(false); // Clear logout flag on successful login
    
    // Check if this is a first-time login
    await checkFirstTimeLogin(userInfo);
    
    // Post to local backend
    try {
      await postLocalLogin(userInfo);
    } catch (err) {
      // Don't fail the auth process if postLocalLogin fails
      // Just log it and continue - user can manually restart if needed
      console.error('[AuthContext] postLocalLogin failed during auth success, continuing anyway:', err);
      setError('Coordinator initialization may have failed. You may need to restart manually.');
    }
  }, [isAuthenticated, fetchUserInfo, postLocalLogin, checkFirstTimeLogin]);

  // Manual restart coordinator function
  const restartCoordinator = useCallback(async () => {
    console.log('[AuthContext] Manual coordinator restart requested...');
    setError(null);
    
    try {
      const result = await api.restartCoordinator();
      console.log('[AuthContext] Coordinator restart successful:', result);
      
      // After restart, ensure user info is fresh
      const userInfo = await fetchUserInfo();
      if (userInfo) {
        await postLocalLogin(userInfo);
      }
      
    } catch (err) {
      console.error('[AuthContext] Coordinator restart failed:', err);
      setError(`Failed to restart coordinator: ${err instanceof Error ? err.message : 'Unknown error'}`);
      throw err; // Re-throw so caller can handle
    }
  }, [fetchUserInfo, postLocalLogin]);

  // Function to hide onboarding modal
  const hideOnboarding = useCallback(() => {
    setShowOnboarding(false);
    // Mark onboarding as completed in localStorage
    localStorage.setItem('denker_onboarding_completed', 'true');
  }, []);

  // Function to show onboarding modal on demand
  const showOnboardingModal = useCallback(() => {
    console.log('[AuthContext] Showing onboarding modal on demand');
    setShowOnboarding(true);
  }, []);

  // --- IPC Interaction Functions ---
  const login = useCallback(async () => {
    console.log('[AuthContext] Initiating login via window.electron.login');
    setError(null); // Clear previous errors
    setIsFromLogout(false); // Reset logout flag when starting new login
    authSuccessHandledRef.current = false; // Reset auth success flag for new login attempt
    setIsLoading(true); // Show loading indicator while external browser is open
    try {
      // Use the renamed 'login' function exposed by preload
      const result = await (window as any).electron?.login?.(); 
      if (result && result.success) {
        console.log('[AuthContext] Login process initiated successfully via IPC.');
        // Authentication state will be updated by 'auth-successful' or 'auth-failed' IPC events
      } else {
        console.error('[AuthContext] Failed to initiate login process via IPC:', result?.error);
        setError(result?.error || 'Failed to start login process.');
        setIsLoading(false);
      }
    } catch (e) {
      console.error('[AuthContext] Error during login IPC call:', e);
      setError('Login initiation failed. Please try again.');
      setIsLoading(false);
    }
  }, []);

  const logout = useCallback(async () => {
    console.log('[AuthContext] Logout requested');
    setIsLoading(true); // Show loading during logout
    setIsFromLogout(true); // Set this early to show proper message
    
    try {
      // Clear both token and user info caches
      clearTokenCache();
      clearUserInfoCache();
      
      // Call Electron logout if available
      if ((window as any).electron?.logout) {
        await (window as any).electron.logout();
      }
      
      setIsAuthenticated(false);
      setUser(null);
      setError(null);
      setBackendReady(false);
      
      // Add a small delay to show the logout message
      setTimeout(() => {
        setIsLoading(false);
      }, 800);
      
      console.log('[AuthContext] Logout completed');
    } catch (error) {
      console.error('[AuthContext] Error during logout:', error);
      setError('Logout failed');
      setIsLoading(false);
    }
  }, []);

  // --- Effect for Initial Auth Check & IPC Listeners ---
  useEffect(() => {
    // Skip all authentication logic for subwindow
    if (isSubWindow) {
      console.log('[AuthContext] Subwindow detected, skipping authentication flow');
      setIsAuthenticated(true); // Mark as authenticated for subwindow
      setIsLoading(false);
      return;
    }
    
    let isMounted = true;
    let authCheckCompleted = false;
    console.log('[AuthContext] Running initial effect setup...');

    // 1. Backend Readiness Check First
    const setupBackendListeners = () => {
      // Listen for backend ready event
      const cleanupBackendReady = (window as any).electron?.onBackendReady?.(() => {
        console.log('[AuthContext] Backend is ready, proceeding with auth check');
        if (isMounted && !authCheckCompleted) {
          setBackendReady(true);
         
          // Trigger auth check when backend becomes ready
          performAuthCheck();
        }
      });

      // Listen for backend failure events
      const cleanupBackendFailed = (window as any).electron?.onBackendFailed?.((errorMessage: string) => {
        console.error('[AuthContext] Backend failed:', errorMessage);
        if (isMounted) {
          setBackendReady(false);
          setBackendError(errorMessage);
          setError(`Backend initialization failed: ${errorMessage}`);
          setIsLoading(false);
        }
      });

      // Listen for backend stopped events
      const cleanupBackendStopped = (window as any).electron?.onBackendStopped?.((message: string) => {
        console.warn('[AuthContext] Backend stopped:', message);
        if (isMounted) {
          setBackendReady(false);
          setError(`Backend stopped: ${message}`);
          setIsLoading(false);
        }
      });

      return { cleanupBackendReady, cleanupBackendFailed, cleanupBackendStopped };
    };

    // 2. Initial Backend Status Check
    const checkInitialBackendStatus = async () => {
      try {
        const isReady = await (window as any).electron?.isBackendReady?.();
        if (isMounted) {
          setBackendReady(isReady);
          console.log(`[AuthContext] Initial backend status: ${isReady ? 'ready' : 'not ready'}`);
          return isReady;
        }
      } catch (error) {
        console.error('[AuthContext] Error checking initial backend status:', error);
        if (isMounted) {
          setBackendReady(false);
          setBackendError('Failed to check backend status');
        }
      }
      return false;
    };

    // 3. Consolidated Auth Check (only called once per backend ready state)
    const performAuthCheck = async () => {
      if (authCheckCompleted) {
        console.log('[AuthContext] Auth check already completed, skipping duplicate');
        return;
      }
      
      authCheckCompleted = true;
      console.log('[AuthContext] Performing auth check...');
      
      // Add a small delay to ensure Electron processes are fully initialized
      if (window.electron) {
        console.log('[AuthContext] Detected Electron environment, adding startup delay...');
        await new Promise(resolve => setTimeout(resolve, 500)); // 500ms delay
      }
      
      const token = await getAccessToken();
      if (isMounted) {
        if (token) {
          console.log('[AuthContext] Auth check: Token found, initiating auth success flow...');
          try {
            authSuccessHandledRef.current = true; // Mark as handled to prevent IPC duplicate
            await handleAuthSuccess();
            console.log('[AuthContext] Auth success flow completed successfully.');
          } catch (error) {
            console.error('[AuthContext] Error during auth success flow:', error);
            // Clear caches on auth success failure
            clearTokenCache();
            clearUserInfoCache();
            setError('Authentication setup failed. Please try logging in again.');
            setIsAuthenticated(false);
            setUser(null);
          }
        } else {
          console.log('[AuthContext] Auth check: No token found.');
          setIsAuthenticated(false);
          setUser(null);
        }
        setIsLoading(false);
      }
    };

    // 4. Setup all listeners first
    const backendCleanups = setupBackendListeners();

    // Setup auth listeners
    console.log('[AuthContext] Setting up auth IPC listeners...');
    const cleanupSuccess = (window as any).electron?.onAuthSuccessful?.(async () => {
      console.log('[AuthContext] Received auth-successful IPC.');
      if (isMounted && !authSuccessHandledRef.current) {
        console.log('[AuthContext] Processing auth-successful IPC...');
        authSuccessHandledRef.current = true;
        
        // Clear any previous errors and ensure loading state for processing
        setError(null);
        setIsLoading(true);
        
        try {
          await handleAuthSuccess();
          console.log('[AuthContext] Auth-successful IPC processing completed.');
        } catch (error) {
          console.error('[AuthContext] Error processing auth-successful IPC:', error);
          setError('Authentication processing failed. Please try again.');
        } finally {
          setIsLoading(false);
        }
      } else {
        console.log('[AuthContext] Skipping auth-successful IPC - already handled or component unmounted');
      }
    });

    const cleanupFailed = (window as any).electron?.onAuthFailed?.((errorInfo: any) => {
      console.error('[AuthContext] Received auth-failed IPC:', errorInfo);
      if (isMounted) {
        const errorMessage = errorInfo?.error_description || errorInfo?.error || 'Authentication failed.';
        
        // Check for email verification errors
        if (errorMessage.includes('Please verify your email') || 
            errorMessage.includes('email_not_verified') ||
            errorMessage.includes('verify') ||
            errorInfo?.error === 'access_denied' && errorMessage.includes('email')) {
          console.log('[AuthContext] Email verification required, redirecting...');
          // Redirect to email verification page
          window.location.href = '/email-verification';
          return;
        }
        
        // Check for signup-related errors that might need verification
        if (errorMessage.includes('signup') || 
            errorMessage.includes('registration') ||
            errorMessage.includes('account creation')) {
          console.log('[AuthContext] Signup detected, might need email verification');
          setError('Account created successfully! Please check your email for verification instructions.');
        } else {
          setError(errorMessage);
        }
        
        setIsAuthenticated(false);
        setUser(null);
        setIsLoading(false);
        // Reset auth success handled flag so next attempt can succeed
        authSuccessHandledRef.current = false;
      }
    });

    const cleanupLogout = (window as any).electron?.onAuthLoggedOut?.(() => {
      console.log('[AuthContext] Received auth-logged-out IPC.');
      if (isMounted) {
        // Clear both token and user info caches when logout IPC is received
        clearTokenCache();
        clearUserInfoCache();
        
        setError(null); 
        setIsAuthenticated(false);
        setUser(null);
        setIsLoading(false); // Immediately stop loading for logout
        setIsFromLogout(true); // Mark as coming from logout
        // Reset flags to allow fresh authentication
        authCheckCompleted = false;
        authSuccessHandledRef.current = false;
        console.log('[AuthContext] Auth state reset after logout.');
      }
    });

    // 5. Check backend status and proceed accordingly
    checkInitialBackendStatus().then((isReady) => {
      if (!isMounted) return;
      
      // If backend is already ready, proceed with auth check immediately
      if (isReady) {
        console.log('[AuthContext] Backend already ready, proceeding with auth check');
        performAuthCheck();
      } else {
        console.log('[AuthContext] Backend not ready yet, waiting for ready signal...');
        // Auth check will be triggered by backend-ready event
      }
    });

    // Cleanup function
    return () => {
      console.log('[AuthContext] Cleaning up effect.');
      isMounted = false;
      cleanupSuccess?.();
      cleanupFailed?.();
      cleanupLogout?.();
      backendCleanups?.cleanupBackendReady?.();
      backendCleanups?.cleanupBackendFailed?.();
      backendCleanups?.cleanupBackendStopped?.();
    };
  }, [isSubWindow]); // Include isSubWindow dependency

  // Add automatic timeout to prevent infinite loading - moved to top level to follow Rules of Hooks
  useEffect(() => {
    if (isLoading) {
      let loadingDuration = 10000; // Default to 10 seconds
      
      if (backendError) {
        loadingDuration = 0; // No timeout if backend error
      } else if (!backendReady) {
        loadingDuration = 15000; // Increased timeout for backend readiness
      } else if (backendReady && !isAuthenticated) {
        if (isFromLogout) {
          // Much shorter timeout for logout scenarios - user just wants to log out
          loadingDuration = 1000;
        } else {
          // Longer timeout when user might be signing up for the first time
          loadingDuration = 60000; // 60 seconds for potential signup/email verification flow
        }
      }

      if (loadingDuration > 0) {
        const maxLoadingTimeout = setTimeout(() => {
          console.warn('[AuthContext] Loading timeout reached, forcing completion');
          setIsLoading(false);
          if (!isAuthenticated && !backendError && !isFromLogout) {
            // More helpful message for signup timeout (but not for logout)
            setError('Authentication is taking longer than expected. If you\'re signing up, please check your email for verification and try logging in again.');
          }
        }, loadingDuration);

        return () => clearTimeout(maxLoadingTimeout);
      }
    }
  }, [isLoading, backendError, backendReady, isAuthenticated, isFromLogout]);

  // Provide the context value to children
  const value = {
    isAuthenticated,
    isLoading,
    error,
    user, // Provide user info
    isFromLogout,
    showOnboarding,
    login,
    logout,
    getAccessToken,
    restartCoordinator,
    hideOnboarding,
    showOnboardingModal,
  };

  // Show enhanced loading screen during initial startup (but not for subwindow)
  if (isLoading && !isSubWindow) {
    let loadingMessage = "Welcome to Denker!";
    let showDetailedSteps = true;
    let loadingDuration = 10000; // Reduced to 10 seconds for better UX with unstable networks
    
    if (backendError) {
      loadingMessage = "Oops, something went wrong";
      showDetailedSteps = false;
      loadingDuration = 0;
    } else if (!backendReady) {
      loadingMessage = "Setting up your AI workspace...";
      showDetailedSteps = true;
      loadingDuration = 8000; // Reduced timeout for backend readiness
    } else if (backendReady && !isAuthenticated) {
      // Consider logout context for better UX
      if (isFromLogout) {
        loadingMessage = "Logging out...";
        showDetailedSteps = false;
        loadingDuration = 1000; // Shorter logout timeout
      } else {
        loadingMessage = "Signing you in...";
        showDetailedSteps = false;
        loadingDuration = 2000; // Shorter auth timeout for unstable networks
      }
    }
    
    return (
      <LoadingScreen 
        message={loadingMessage}
        showDetailedSteps={showDetailedSteps}
        duration={loadingDuration}
      />
    );
  }

  // Show error state if backend failed and we're not loading
  if (backendError && !isLoading) {
    return (
      <div style={{ 
        display: 'flex', 
        flexDirection: 'column', 
        alignItems: 'center', 
        justifyContent: 'center', 
        minHeight: '100vh',
        padding: '20px',
        textAlign: 'center'
      }}>
        <h2>Backend Startup Failed</h2>
        <p>{backendError}</p>
        <p>Please restart the application or contact support if the problem persists.</p>
        <button 
          onClick={() => (window as any).electron?.restartApp?.()}
          style={{ 
            marginTop: '20px',
            padding: '10px 20px',
            backgroundColor: '#1976d2',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer'
          }}
        >
          Restart Application
        </button>
      </div>
    );
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

// Custom hook to use the AuthContext
export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

// Optional: Higher-Order Component for protecting routes
export const withAuth = <P extends object>(Component: React.ComponentType<P>): React.FC<P> => {
  return (props: P) => {
    const { isAuthenticated, isLoading } = useAuth();
    const navigate = useNavigate(); // Assuming react-router v6

    useEffect(() => {
      if (!isLoading && !isAuthenticated) {
        console.log('[withAuth] Not authenticated, redirecting to login.');
        navigate('/login'); // Redirect to your login route
      }
    }, [isLoading, isAuthenticated, navigate]);

    return <Component {...props} />;
  };
};
 