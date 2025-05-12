import React, { createContext, useState, useEffect, useContext, ReactNode, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { CircularProgress } from '@mui/material';

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
  login: () => void;
  logout: () => void;
  getAccessToken: () => Promise<string | null>;
  // Optional: Add a function to refetch user info if needed
  // refreshUserInfo: () => Promise<void>; 
}

// Create the context with a default undefined value to ensure it's used within a provider
const AuthContext = createContext<AuthContextType | undefined>(undefined);

// Define the props for the provider component
interface AuthProviderProps {
  children: ReactNode;
}

// Create the provider component
export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(true); // Start loading until initial check is done
  const [error, setError] = useState<string | null>(null);
  const [user, setUser] = useState<UserInfo | null>(null); // Add user state

  // Function to fetch user info via IPC
  const fetchUserInfo = useCallback(async () => {
    console.log('[AuthContext] Fetching user info via IPC...');
    try {
      const userInfo = await (window as any).electron?.getUserInfo?.();
      if (userInfo) {
        console.log('[AuthContext] User info received:', userInfo);
        setUser(userInfo);
      } else {
        console.log('[AuthContext] No user info returned from main process.');
        setUser(null);
      }
    } catch (e) {
      console.error('[AuthContext] Error fetching user info:', e);
      setUser(null); // Clear user info on error
      // Optionally set a specific error message
      // setError('Failed to load user profile.');
    }
  }, []);

  // --- IPC Interaction Functions ---
  const login = useCallback(async () => {
    console.log('[AuthContext] Initiating login via window.electron.login');
    setError(null); // Clear previous errors
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
    console.log('[AuthContext] Initiating logout via window.electron.logout');
    setError(null);
    setIsLoading(true);
    setUser(null); // Clear user info immediately on logout initiation
    try {
      await (window as any).electron?.logout?.(); // Use cast to any to bypass type checking for window.electron
      // State changes (isAuthenticated=false) will be triggered by the 'auth-logged-out' IPC message
    } catch (e) {
      console.error('[AuthContext] Error during logout IPC call:', e);
      setError('Logout failed. Please try again.');
      setIsLoading(false); // Still set loading false on error
    }
  }, []);

  const getAccessToken = useCallback(async (): Promise<string | null> => {
    console.log('[AuthContext] Requesting token via window.electron.getAccessToken');
    try {
      const token = await (window as any).electron?.getAccessToken?.(); // Use cast to any to bypass type checking for window.electron
      if (!token) {
        console.log('[AuthContext] No access token returned from main process.');
        // If no token, ensure we are marked as not authenticated
        if (isAuthenticated) {
          setIsAuthenticated(false);
        }
        return null;
      }
      console.log('[AuthContext] Received access token from main process.');
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

  // --- Effect for Initial Auth Check & IPC Listeners ---
  useEffect(() => {
    let isMounted = true;
    console.log('[AuthContext] Running initial effect setup...');

    // 1. Initial Check: See if we already have a valid token
    const checkInitialAuth = async () => {
      console.log('[AuthContext] Performing initial token check...');
      setIsLoading(true);
      const token = await getAccessToken();
      if (isMounted) {
        if (token) {
          console.log('[AuthContext] Initial check: Token found, setting authenticated.');
          setIsAuthenticated(true);
          await fetchUserInfo(); // Fetch user info if token exists
        } else {
          console.log('[AuthContext] Initial check: No token found.');
          setIsAuthenticated(false);
          setUser(null); // Ensure user is null if not authenticated
        }
        // Don't set isLoading false immediately, wait for listeners
      }
    };

    // 2. Setup IPC Listeners
    console.log('[AuthContext] Setting up IPC listeners...');
    const cleanupSuccess = (window as any).electron?.onAuthSuccessful?.(async () => { // Make async
      console.log('[AuthContext] Received auth-successful IPC.');
      if (isMounted) {
        setError(null);
        setIsAuthenticated(true);
        await fetchUserInfo(); // Fetch user info on successful login
        setIsLoading(false);
      }
    });

    const cleanupFailed = (window as any).electron?.onAuthFailed?.((errorInfo: any) => {
      console.error('[AuthContext] Received auth-failed IPC:', errorInfo);
      if (isMounted) {
        setError(errorInfo?.error_description || errorInfo?.error || 'Authentication failed.');
        setIsAuthenticated(false);
        setUser(null); // Clear user info on auth failure
        setIsLoading(false);
      }
    });

    const cleanupLogout = (window as any).electron?.onAuthLoggedOut?.(() => {
      console.log('[AuthContext] Received auth-logged-out IPC.');
      if (isMounted) {
        setError(null); 
        setIsAuthenticated(false);
        setUser(null); // Ensure user info is cleared on logout confirmation
        setIsLoading(false);
      }
    });

    // Run initial check first, then set loading state based on listeners being ready
    checkInitialAuth().finally(() => {
      if (isMounted) {
        // Set loading false only after the initial check AND listeners are set up
        console.log('[AuthContext] Initial check complete, setting loading to false.');
        setIsLoading(false);
      }
    });

    // Cleanup function
    return () => {
      console.log('[AuthContext] Cleaning up effect.');
      isMounted = false;
      cleanupSuccess?.();
      cleanupFailed?.();
      cleanupLogout?.();
    };
  }, [getAccessToken, fetchUserInfo]); // Add fetchUserInfo to dependencies

  // Provide the context value to children
  const value = {
    isAuthenticated,
    isLoading,
    error,
    user, // Provide user info
    login,
    logout,
    getAccessToken,
  };

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
 