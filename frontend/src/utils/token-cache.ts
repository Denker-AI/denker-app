/**
 * Token Cache System to prevent multiple simultaneous getAccessToken calls
 * This solves the issue where multiple components request tokens at the same time,
 * causing performance problems and static loading screens.
 */

interface TokenCacheEntry {
  token: string | null;
  timestamp: number;
  expiresAt: number;
}

class TokenCache {
  private cache: TokenCacheEntry | null = null;
  private pendingRequest: Promise<string | null> | null = null;
  private readonly CACHE_DURATION_MS = 30 * 1000; // 30 seconds cache
  private readonly BUFFER_MS = 5 * 1000; // 5 seconds buffer before expiry
  private isLoggedOut: boolean = false; // Track logout state

  /**
   * Get access token with caching to prevent multiple simultaneous calls
   */
  async getAccessToken(): Promise<string | null> {
    // If we're in a logged out state, don't return cached tokens
    if (this.isLoggedOut) {
      console.log('[TokenCache] Logged out state - clearing cache and fetching fresh token');
      this.cache = null;
      this.isLoggedOut = false; // Reset flag after clearing
    }

    // Check if we have a valid cached token
    if (this.cache && this.isTokenValid(this.cache)) {
      console.log('[TokenCache] Using cached token to prevent duplicate getAccessToken call');
      return this.cache.token;
    }

    // If there's already a pending request, return that promise
    if (this.pendingRequest) {
      console.log('[TokenCache] Joining existing getAccessToken request to prevent duplicate');
      return this.pendingRequest;
    }

    // Make a new request and cache the promise
    console.log('[TokenCache] Making new getAccessToken request');
    this.pendingRequest = this.fetchTokenFromElectron();

    try {
      const token = await this.pendingRequest;
      
      // Only cache valid tokens
      if (token && token !== 'dev-mode-token') {
        this.cache = {
          token,
          timestamp: Date.now(),
          expiresAt: Date.now() + this.CACHE_DURATION_MS
        };
        console.log('[TokenCache] Token fetched and cached successfully');
      } else {
        console.log('[TokenCache] Token fetched but not cached (null or dev token)');
      }
      
      return token;
    } catch (error) {
      console.error('[TokenCache] Error fetching token:', error);
      // Clear cache on error
      this.cache = null;
      throw error;
    } finally {
      // Clear the pending request
      this.pendingRequest = null;
    }
  }

  /**
   * Check if a cached token is still valid
   */
  private isTokenValid(cacheEntry: TokenCacheEntry): boolean {
    const now = Date.now();
    return now < (cacheEntry.expiresAt - this.BUFFER_MS);
  }

  /**
   * Fetch token directly from Electron
   */
  private async fetchTokenFromElectron(): Promise<string | null> {
    try {
      if ((window as any).electron?.getAccessToken) {
        const token = await (window as any).electron.getAccessToken();
        return token;
      }
      
      // Development fallback
      if (import.meta.env.DEV) {
        console.log('[TokenCache] Dev mode fallback token');
        return 'dev-mode-token';
      }
      
      return null;
    } catch (error) {
      console.error('[TokenCache] Error calling electron.getAccessToken:', error);
      
      // Development fallback on error
      if (import.meta.env.DEV) {
        return 'dev-mode-token';
      }
      
      throw error;
    }
  }

  /**
   * Clear the token cache (useful for logout or when token becomes invalid)
   */
  clearCache(): void {
    console.log('[TokenCache] Clearing token cache');
    this.cache = null;
    this.pendingRequest = null;
    this.isLoggedOut = true; // Mark as logged out to prevent stale cache usage
  }

  /**
   * Force refresh the token (bypass cache)
   */
  async refreshToken(): Promise<string | null> {
    console.log('[TokenCache] Force refreshing token');
    this.clearCache();
    return this.getAccessToken();
  }
}

// Export singleton instance
export const tokenCache = new TokenCache();

/**
 * Convenience function to get cached access token
 * Use this instead of calling window.electron.getAccessToken directly
 */
export const getCachedAccessToken = () => tokenCache.getAccessToken();

/**
 * Clear token cache (for logout scenarios)
 */
export const clearTokenCache = () => tokenCache.clearCache();

/**
 * Force refresh token (bypass cache)
 */
export const refreshCachedToken = () => tokenCache.refreshToken(); 