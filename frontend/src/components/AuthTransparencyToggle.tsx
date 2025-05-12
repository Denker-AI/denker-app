import { useEffect } from 'react';
import { useAuth0 } from '@auth0/auth0-react';

const AuthTransparencyToggle = () => {
  const { isAuthenticated, isLoading } = useAuth0();

  useEffect(() => {
    // Only toggle transparency when authentication state is finalized (not loading)
    if (!isLoading) {
      if (window.electron && window.electron.toggleTransparency) {
        // If authenticated, make window transparent, otherwise keep it solid
        window.electron.toggleTransparency(isAuthenticated);
        console.log(`Window transparency set to: ${isAuthenticated}`);
      }
    }
  }, [isAuthenticated, isLoading]);

  // This is a utility component with no UI
  return null;
};

export default AuthTransparencyToggle; 