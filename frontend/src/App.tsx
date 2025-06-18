import React, { useEffect } from 'react';
import { Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import { useAuth } from './auth/AuthContext';
import { useAppInitialization } from './hooks/useAppInitialization';

// Components
import { LoadingScreen, OnboardingModal } from './components/Common';
import { 
  FileSystemPermissionProvider, 
  FileSystemActivityProvider 
} from './components/FileSystem';
import AuthTransparencyToggle from './components/AuthTransparencyToggle';

// Pages
import MainWindowNew from './pages/MainWindowNew';
import SubWindow from './pages/SubWindow';
import Login from './pages/Login';
import SettingsPage from './pages/SettingsPage';
import ProfilePage from './pages/ProfilePage';
import FeedbackPage from './pages/FeedbackPage';
import FilesPage from './pages/FilesPage';
import AboutPage from './pages/AboutPage';
import NotFoundPage from './pages/NotFoundPage';
import AuthErrorPage from './pages/AuthErrorPage';
import HelpPage from './pages/HelpPage';
import ContactPage from './pages/ContactPage';
import PrivacyPolicyPage from './pages/PrivacyPolicyPage';
import AuthCallbackPage from './pages/AuthCallbackPage';
import EmailVerificationPage from './pages/EmailVerificationPage';

// Auth guard component with coordinated initialization
const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  const { isAuthenticated, isFromLogout, showOnboarding, hideOnboarding, showOnboardingModal } = useAuth();
  const { isInitialized, isLoading, initializationError, loadingMessage, loadingProgress, isFirstTimeUser } = useAppInitialization();

  // Listen for onboarding events from electron menu
  useEffect(() => {
    const handleShowOnboarding = () => {
      console.log('[ProtectedRoute] Show onboarding event received from menu');
      // Show the onboarding modal directly
      showOnboardingModal();
    };

    if (window.electron?.onShowOnboarding) {
      const cleanup = window.electron.onShowOnboarding(handleShowOnboarding);
      return cleanup;
    }
  }, [showOnboardingModal]);

  console.log('[ProtectedRoute] Status:', { 
    isInitialized, 
    isLoading, 
    isAuthenticated, 
    isFromLogout,
    initializationError,
    loadingProgress,
    isFirstTimeUser
  });

  // Show loading screen while initializing
  if (isLoading || !isInitialized) {
    console.log('[ProtectedRoute] Rendering LoadingScreen - still initializing');
    
    // Create user-friendly error messages for authentication issues
    let displayMessage = loadingMessage;
    if (initializationError) {
      if (initializationError.includes('Authentication failed') || 
          initializationError.includes('Invalid token') ||
          initializationError.includes('User account not found') ||
          initializationError.includes('Please log in again')) {
        displayMessage = 'Oops! Please sign in to continue';
      } else if (initializationError.includes('Backend') || 
                 initializationError.includes('startup') ||
                 initializationError.includes('initialization')) {
        displayMessage = 'Something went wrong during startup';
      } else {
        displayMessage = 'Something went wrong, please try again';
      }
    }
    
    return (
      <LoadingScreen 
        message={displayMessage}
        showDetailedSteps={!initializationError && isFirstTimeUser} // Show detailed tips only for first-time users
        progress={loadingProgress}
        duration={isFirstTimeUser ? 10000 : 3000} // 10 seconds for first-time users, 3 seconds for returning users
      />
    );
  }

  // Check for authentication-related errors that should redirect to login
  const isAuthError = initializationError && (
    initializationError.includes('User account not found') ||
    initializationError.includes('Please log in again') ||
    initializationError.includes('Authentication failed') ||
    initializationError.includes('Invalid token') ||
    initializationError.includes('Login required')
  );

  // If authentication error or not authenticated after successful initialization, redirect to login
  if (!isAuthenticated || isAuthError) {
    console.log('[ProtectedRoute] Authentication issue detected, redirecting to /login');
    const loginPath = isFromLogout ? '/login?from=logout' : '/login';
    return <Navigate to={loginPath} replace />;
  }

  // If initialization failed with non-auth error, show error page
  if (initializationError) {
    console.log('[ProtectedRoute] Non-authentication initialization error:', initializationError);
    
    // Create user-friendly error display
    let errorTitle = 'Something went wrong';
    let errorDescription = 'Please try refreshing the page or restarting the application.';
    
    if (initializationError.includes('Network') || initializationError.includes('connection')) {
      errorTitle = 'Connection Issue';
      errorDescription = 'Please check your internet connection and try again.';
    } else if (initializationError.includes('Backend') || initializationError.includes('server')) {
      errorTitle = 'Service Unavailable';
      errorDescription = 'Our servers are experiencing issues. Please try again in a moment.';
    } else if (initializationError.includes('timeout')) {
      errorTitle = 'Taking Longer Than Expected';
      errorDescription = 'The app is taking longer to load. Please try refreshing.';
    }
    
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
        <h2>{errorTitle}</h2>
        <p style={{ marginBottom: '10px', maxWidth: '400px' }}>{errorDescription}</p>
        <p style={{ fontSize: '0.9em', color: '#666', marginBottom: '20px' }}>
          Error details: {initializationError}
        </p>
        <button 
          onClick={() => window.location.reload()}
          style={{ 
            marginTop: '10px',
            padding: '10px 20px',
            backgroundColor: '#1976d2',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer'
          }}
        >
          Try Again
        </button>
      </div>
    );
  }

  console.log('[ProtectedRoute] Fully initialized and authenticated, rendering children');
  return (
    <>
      <OnboardingModal 
        open={showOnboarding} 
        onClose={hideOnboarding} 
      />
      {children}
    </>
  );
};

const App: React.FC = () => {
  console.log('[App] App component rendering...');
  
  return (
    <FileSystemPermissionProvider>
      <FileSystemActivityProvider>
        <div className="App">
          <AuthTransparencyToggle />
          <Routes>
            {/* Public routes */}
            <Route path="/login" element={<Login />} />
            <Route path="/auth-callback" element={<AuthCallbackPage />} />
            <Route path="/auth-error" element={<AuthErrorPage />} />
            <Route path="/email-verification" element={<EmailVerificationPage />} />
            <Route path="/help" element={<HelpPage />} />
            <Route path="/contact" element={<ContactPage />} />
            <Route path="/privacy-policy" element={<PrivacyPolicyPage />} />
            
            {/* Protected routes */}
            <Route path="/" element={<ProtectedRoute><MainWindowNew /></ProtectedRoute>} />
            <Route path="/subwindow" element={<SubWindow />} />
            <Route path="/settings" element={<ProtectedRoute><SettingsPage /></ProtectedRoute>} />
            <Route path="/profile" element={<ProtectedRoute><ProfilePage /></ProtectedRoute>} />
            <Route path="/feedback" element={<ProtectedRoute><FeedbackPage /></ProtectedRoute>} />
            <Route path="/files" element={<ProtectedRoute><FilesPage /></ProtectedRoute>} />
            <Route path="/about" element={<ProtectedRoute><AboutPage /></ProtectedRoute>} />
            
            {/* Catch all route */}
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </div>
      </FileSystemActivityProvider>
    </FileSystemPermissionProvider>
  );
};

export default App; 