// Global user info cache to prevent excessive Auth0 API calls
let cachedUserInfo: any = null;
let isUserInfoCached = false;

export const getUserInfoCached = async (): Promise<any> => {
  // Return cached user info if available
  if (isUserInfoCached && cachedUserInfo) {
    console.log('[UserInfoCache] Using cached user info to prevent Auth0 rate limits');
    return cachedUserInfo;
  }

  // Otherwise fetch from Electron and cache it
  if ((window as any).electron?.getUserInfo) {
    try {
      console.log('[UserInfoCache] Fetching user info from Auth0 (first time)...');
      const userInfo = await (window as any).electron.getUserInfo();
      if (userInfo) {
        cachedUserInfo = userInfo;
        isUserInfoCached = true;
        console.log('[UserInfoCache] User info cached successfully');
        return userInfo;
      }
    } catch (error) {
      console.error('[UserInfoCache] Error fetching user info:', error);
      // Don't cache failed attempts
      return null;
    }
  }

  return null;
};

export const clearUserInfoCache = (): void => {
  console.log('[UserInfoCache] Clearing cached user info');
  cachedUserInfo = null;
  isUserInfoCached = false;
};

export const isUserInfoCacheValid = (): boolean => {
  return isUserInfoCached && cachedUserInfo !== null;
}; 