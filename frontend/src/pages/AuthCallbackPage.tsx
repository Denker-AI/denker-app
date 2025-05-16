import React, { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { LoadingScreen } from '../components/Common';

const AuthCallbackPage: React.FC = () => {
  const { isAuthenticated, isLoading, error } = useAuth();
  const navigate = useNavigate();
  const devCallbackProcessedRef = useRef(false);

  useEffect(() => {
    const processDevCallbackIfNeeded = async () => {
      const isElectron = typeof window.electron !== 'undefined';
      const canProcessDevCallback = isElectron && typeof window.electron.devProcessAuth0Callback === 'function';
      
      if (import.meta.env.DEV && canProcessDevCallback && !devCallbackProcessedRef.current) {
        const searchParams = new URLSearchParams(window.location.search);
        const code = searchParams.get('code');
        const state = searchParams.get('state');

        if (code && state) {
          devCallbackProcessedRef.current = true;
          console.log('[AuthCallbackPage][DEV] Found code and state in URL. Sending to main process...');
          try {
            await window.electron.devProcessAuth0Callback({ code, state });
            window.history.replaceState({}, document.title, window.location.pathname + window.location.hash);
            console.log('[AuthCallbackPage][DEV] Params sent to main. Waiting for AuthContext update.');
          } catch (ipcError) {
            console.error('[AuthCallbackPage][DEV] Error invoking devProcessAuth0Callback IPC:', ipcError);
            navigate('/login?error=ipc_dev_callback_failed', { replace: true });
          }
        } else {
          // No code/state in URL in dev mode, nothing to do for dev callback path
          // This case might occur if navigated to #/callback manually in dev
        }
      }
    };

    processDevCallbackIfNeeded();

    console.log('[AuthCallbackPage] Status update: isLoading=', isLoading, 'isAuthenticated=', isAuthenticated, 'error=', error);
    
    if (!isLoading) {
      if (isAuthenticated) {
        console.log('[AuthCallbackPage] Auth successful (isAuthenticated=true, isLoading=false), navigating to /');
        navigate('/', { replace: true });
      } else {
        console.log('[AuthCallbackPage] Auth not successful or was not applicable (isLoading=false, isAuthenticated=false), navigating to /login. Error:', error);
        if(devCallbackProcessedRef.current && !error) {
          console.warn('[AuthCallbackPage] Dev callback processed, not loading, not authenticated, and no specific error. Proceeding to /login.');
        }
        navigate('/login', { replace: true });
      }
    }
  }, [isAuthenticated, isLoading, error, navigate]);

  return <LoadingScreen message="Finalizing login (dev mode callback handling)..." />;
};

export default AuthCallbackPage; 