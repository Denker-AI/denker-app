import React, { useEffect } from 'react';
import { Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import { useAuth } from './auth/AuthContext';

// Components
import { LoadingScreen } from './components/Common';
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
import TestPage from './pages/TestPage';
import AuthCallbackPage from './pages/AuthCallbackPage';

// Auth guard component
const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  const { isAuthenticated, isLoading } = useAuth();
  console.log('[ProtectedRoute] Status: isLoading=', isLoading, 'isAuthenticated=', isAuthenticated);

  if (isLoading) {
    console.log('[ProtectedRoute] Rendering LoadingScreen because isLoading is true.');
    return <LoadingScreen message="Checking authentication..." />;
  }

  if (!isAuthenticated) {
    console.log('[ProtectedRoute] Not authenticated, redirecting to /login because isAuthenticated is false.');
    return <Navigate to="/login" replace />;
  }

  console.log('[ProtectedRoute] Authenticated, rendering children.');

  return <>{children}</>;
};

// Logout route component
const LogoutRoute = () => {
  const { logout, isLoading, isAuthenticated } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    console.log('[Logout Route] Calling logout...');
    logout();
  }, [logout]);

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      console.log('[Logout Route] Logout confirmed by context, navigating to /login');
      navigate('/login', { replace: true });
    }
  }, [isLoading, isAuthenticated, navigate]);

  return <LoadingScreen message="Logging out..." />;
};

function App() {
  console.log('[App.tsx] Mounted. Vite DEV mode:', import.meta.env.DEV, 'Vite MODE:', import.meta.env.MODE);
  const navigate = useNavigate();
  const isElectron = window.electron !== undefined;

  // Listen for navigation events from Electron main process
  useEffect(() => {
    if (isElectron) {
      const handleNavigate = (event: CustomEvent) => {
        const path = event.detail;
        console.log('Received navigate event to:', path);
        
        // Handle special paths like logout
        if (path === '/logout') {
          console.log('Processing logout navigation event');
          navigate(path);
        } 
        // Handle feedback path
        else if (path === '/feedback') {
          console.log('Processing feedback navigation event');
          navigate(path);
        }
        // Handle all other paths
        else {
          navigate(path);
        }
      };

      window.addEventListener('navigate', handleNavigate as EventListener);
      
      return () => {
        window.removeEventListener('navigate', handleNavigate as EventListener);
      };
    }
  }, [navigate, isElectron]);

  return (
    <>
      {/* This component manages window transparency based on auth state */}
      <AuthTransparencyToggle />
      
      <Routes>
        {/* Public routes that need to be outside the FileSystemProviders */}
        <Route path="/login" element={<Login />} />
        <Route path="/callback" element={<AuthCallbackPage />} />
        <Route path="/404" element={<NotFoundPage />} />
        <Route path="/auth/error" element={<AuthErrorPage />} />
        <Route path="/subwindow" element={<SubWindow />} />
        <Route path="/logout" element={<LogoutRoute />} />
        
        {/* Routes that need FileSystem providers */}
        <Route
          path="*"
          element={
    <div className="app-container">
      <FileSystemPermissionProvider>
        <FileSystemActivityProvider>
          <Routes>
            <Route
              path="/"
              element={
                <ProtectedRoute>
                  <MainWindowNew />
                </ProtectedRoute>
              }
            />
            <Route path="/test" element={<TestPage />} />
            <Route
              path="/settings"
              element={
                <ProtectedRoute>
                  <SettingsPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/profile"
              element={
                <ProtectedRoute>
                  <ProfilePage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/feedback"
              element={
                <ProtectedRoute>
                  <FeedbackPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/files"
              element={
                <ProtectedRoute>
                  <FilesPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/about"
              element={
                <ProtectedRoute>
                  <AboutPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/help"
              element={
                <ProtectedRoute>
                  <HelpPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/contact"
              element={
                <ProtectedRoute>
                  <ContactPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/privacy"
              element={
                <ProtectedRoute>
                  <PrivacyPolicyPage />
                </ProtectedRoute>
              }
            />
                    {/* Catch remaining routes and redirect to 404 */}
            <Route path="*" element={<Navigate to="/404" replace />} />
          </Routes>
        </FileSystemActivityProvider>
      </FileSystemPermissionProvider>
    </div>
          }
        />
      </Routes>
    </>
  );
}

export default App; 