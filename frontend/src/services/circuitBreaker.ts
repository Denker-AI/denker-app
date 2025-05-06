interface CircuitBreakerConfig {
  failureThreshold: number;
  resetTimeout: number;
}

export class CircuitBreaker {
  private isOpen: boolean = false;
  private failureCount: number = 0;
  private lastFailureTime: number = 0;
  private failureThreshold: number;
  private resetTimeout: number;

  constructor(config: CircuitBreakerConfig) {
    this.failureThreshold = config.failureThreshold;
    this.resetTimeout = config.resetTimeout;
    this.forceReset(); // Reset on initialization
  }

  // Check if circuit is open (preventing requests)
  check(): boolean {
    if (this.isOpen) {
      const now = Date.now();
      if (now - this.lastFailureTime > this.resetTimeout) {
        console.log('Circuit breaker: reset timeout reached, allowing retry');
        this.isOpen = false;
        this.failureCount = 0;
        return false;
      }
      return true;
    }
    return false;
  }

  // Record a failure
  failure(): void {
    this.failureCount++;
    this.lastFailureTime = Date.now();

    if (this.failureCount >= this.failureThreshold) {
      console.log(`Circuit breaker: opened after ${this.failureCount} failures`);
      this.isOpen = true;
      // Store the circuit state in session storage
      window.sessionStorage.setItem('network_error_timestamp', Date.now().toString());
    }
  }

  // Record a success
  success(): void {
    if (this.failureCount > 0) {
      this.failureCount = 0;
      if (this.isOpen) {
        console.log('Circuit breaker: closed after successful request');
        this.isOpen = false;
        // Clear the circuit state from session storage
        window.sessionStorage.removeItem('network_error_timestamp');
      }
    }
  }

  // Force reset the circuit breaker
  forceReset(): void {
    console.log('Circuit breaker: forced reset');
    this.isOpen = false;
    this.failureCount = 0;
    this.lastFailureTime = 0;
    window.sessionStorage.removeItem('network_error_timestamp');
  }
} 