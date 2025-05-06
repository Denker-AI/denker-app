import { useCallback } from 'react';

/**
 * RetryOptions - Configuration options for the retry mechanism
 */
export interface RetryOptions {
  /** Maximum number of retry attempts */
  maxRetries?: number;
  /** Initial delay in milliseconds before the first retry */
  initialDelay?: number;
  /** Maximum delay in milliseconds between retries */
  maxDelay?: number;
  /** Factor by which the delay increases with each retry (for exponential backoff) */
  backoffFactor?: number;
  /** Whether to add jitter to delay times to prevent synchronized retries */
  useJitter?: boolean;
}

/**
 * Hook that provides standardized retry logic with exponential backoff.
 * Useful for retrying failed API calls or other async operations.
 */
export const useRetryLogic = (options?: RetryOptions) => {
  // Default retry configuration
  const defaultOptions: Required<RetryOptions> = {
    maxRetries: 3,
    initialDelay: 300,
    maxDelay: 5000,
    backoffFactor: 2,
    useJitter: true,
  };

  // Merge default options with provided options
  const config = { ...defaultOptions, ...options };

  /**
   * Executes a function with retry logic
   * @param fn - Async function to execute with retry logic
   * @param customOptions - Optional override for retry options
   * @returns Promise with the function result
   */
  const executeWithRetry = useCallback(
    async <T>(fn: () => Promise<T>, customOptions?: Partial<RetryOptions>): Promise<T> => {
      // Merge base config with any custom options for this specific call
      const retryConfig = { ...config, ...customOptions };
      const {
        maxRetries,
        initialDelay,
        maxDelay,
        backoffFactor,
        useJitter,
      } = retryConfig;

      let retryCount = 0;
      let delay = initialDelay;

      while (retryCount <= maxRetries) {
        try {
          // Attempt to execute the function
          return await fn();
        } catch (error) {
          // If we've reached max retries, throw the error
          if (retryCount >= maxRetries) {
            console.log(`Maximum retries (${maxRetries}) reached, giving up`);
            throw error;
          }

          // Increment retry counter
          retryCount++;

          // Calculate delay for next retry with optional jitter
          const jitterFactor = useJitter ? 0.5 + Math.random() : 1;
          const nextDelay = Math.min(delay * backoffFactor * jitterFactor, maxDelay);
          
          console.log(`Retry ${retryCount}/${maxRetries} after ${Math.round(delay)}ms delay...`);
          
          // Wait for the delay period
          await new Promise(resolve => setTimeout(resolve, delay));
          
          // Increase delay for next potential retry (exponential backoff)
          delay = nextDelay;
        }
      }

      // This should never be reached due to the return in try block
      throw new Error('Unexpected end of retry loop');
    },
    [config]
  );

  return { executeWithRetry };
};

export default useRetryLogic; 