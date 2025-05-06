import { useState, useEffect, useCallback } from 'react';

/**
 * Circuit breaker configuration options
 */
interface CircuitBreakerConfig {
  /** Number of failures before circuit opens */
  failureThreshold: number;
  /** Time in milliseconds before attempting to reset/half-open circuit */
  resetTimeout: number;
  /** Storage key for persisting circuit breaker state */
  storageKey: string;
}

/**
 * API status states
 */
export enum ApiStatus {
  /** API is functioning normally */
  ONLINE = 'online',
  /** API is experiencing intermittent issues */
  DEGRADED = 'degraded',
  /** API is unreachable */
  OFFLINE = 'offline',
  /** Initial status before any checks are made */
  UNKNOWN = 'unknown'
}

/**
 * Hook for monitoring API health and implementing circuit breaker pattern.
 * Helps prevent cascading failures by temporarily stopping requests after multiple failures.
 */
export const useApiStatus = (config?: Partial<CircuitBreakerConfig>) => {
  // Default configuration
  const defaultConfig: CircuitBreakerConfig = {
    failureThreshold: 8,         // More tolerant threshold (was 10 in original)
    resetTimeout: 15000,         // 15 seconds (was 30 seconds in original)
    storageKey: 'api_circuit_breaker'
  };

  // Merge config with defaults
  const { failureThreshold, resetTimeout, storageKey } = { 
    ...defaultConfig, 
    ...config 
  };

  // State for API status
  const [status, setStatus] = useState<ApiStatus>(ApiStatus.UNKNOWN);
  const [failureCount, setFailureCount] = useState(0);
  const [lastFailureTime, setLastFailureTime] = useState(0);
  const [isCircuitOpen, setIsCircuitOpen] = useState(false);

  // Initialize from session storage
  useEffect(() => {
    const storedState = window.sessionStorage.getItem(storageKey);
    if (storedState) {
      try {
        const parsedState = JSON.parse(storedState);
        setFailureCount(parsedState.failureCount || 0);
        setLastFailureTime(parsedState.lastFailureTime || 0);
        setIsCircuitOpen(parsedState.isCircuitOpen || false);
        
        // Update status based on circuit state
        if (parsedState.isCircuitOpen) {
          setStatus(ApiStatus.OFFLINE);
        } else if (parsedState.failureCount > 0) {
          setStatus(ApiStatus.DEGRADED);
        } else {
          // If we have state but no failures, we're online
          setStatus(ApiStatus.ONLINE);
        }
      } catch (e) {
        console.error('Error parsing circuit breaker state:', e);
        window.sessionStorage.removeItem(storageKey);
      }
    }
  }, [storageKey]);

  // Persist circuit breaker state to session storage
  useEffect(() => {
    if (status !== ApiStatus.UNKNOWN) {
      const state = {
        failureCount,
        lastFailureTime,
        isCircuitOpen,
        status
      };
      window.sessionStorage.setItem(storageKey, JSON.stringify(state));
    }
  }, [failureCount, lastFailureTime, isCircuitOpen, status, storageKey]);

  // Check if circuit should be reset
  useEffect(() => {
    if (isCircuitOpen) {
      const checkInterval = setInterval(() => {
        const now = Date.now();
        if (now - lastFailureTime > resetTimeout) {
          console.log('Circuit breaker: reset timeout reached, half-opening circuit');
          setIsCircuitOpen(false);
          setStatus(ApiStatus.DEGRADED);
        }
      }, 1000); // Check every second
      
      return () => clearInterval(checkInterval);
    }
  }, [isCircuitOpen, lastFailureTime, resetTimeout]);

  /**
   * Check if a request should be allowed to proceed based on circuit state
   * @returns boolean indicating if request should proceed
   */
  const shouldAllowRequest = useCallback(() => {
    if (!isCircuitOpen) {
      return true;
    }

    // If circuit is open, check if reset timeout has passed
    const now = Date.now();
    if (now - lastFailureTime > resetTimeout) {
      console.log('Circuit breaker: allowing test request in half-open state');
      return true;
    }
    
    return false;
  }, [isCircuitOpen, lastFailureTime, resetTimeout]);

  /**
   * Record a successful API call
   */
  const recordSuccess = useCallback(() => {
    if (failureCount > 0 || isCircuitOpen) {
      console.log('Circuit breaker: recording success, resetting failure count');
      setFailureCount(0);
      setIsCircuitOpen(false);
      setStatus(ApiStatus.ONLINE);
    }
  }, [failureCount, isCircuitOpen]);

  /**
   * Record a failed API call
   */
  const recordFailure = useCallback(() => {
    const newFailureCount = failureCount + 1;
    setFailureCount(newFailureCount);
    setLastFailureTime(Date.now());

    if (newFailureCount >= failureThreshold) {
      console.log(`Circuit breaker: opened after ${newFailureCount} failures`);
      setIsCircuitOpen(true);
      setStatus(ApiStatus.OFFLINE);
    } else if (newFailureCount > 0) {
      setStatus(ApiStatus.DEGRADED);
    }
  }, [failureCount, failureThreshold]);

  /**
   * Reset the circuit breaker manually
   */
  const resetCircuitBreaker = useCallback(() => {
    console.log('Circuit breaker: manual reset');
    setFailureCount(0);
    setLastFailureTime(0);
    setIsCircuitOpen(false);
    setStatus(ApiStatus.ONLINE);
  }, []);

  return {
    apiStatus: status,
    isCircuitOpen,
    failureCount,
    shouldAllowRequest,
    recordSuccess,
    recordFailure,
    resetCircuitBreaker
  };
};

export default useApiStatus; 