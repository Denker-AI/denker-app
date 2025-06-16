import logging
import sys

def setup_logging():
    """Configure logging for the application"""
    # Remove any existing handlers
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Configure root logger
    root_logger.setLevel(logging.DEBUG)
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    
    # Create formatter with more detailed information
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(formatter)
    
    # Add handler to root logger
    root_logger.addHandler(console_handler)
    
    # Explicitly set log levels for all loggers
    loggers = [
        'agents',
        'agents.intention_agent',
        'services',
        'services.vertex_ai',
        'api',
        'api.api_v1',
        'api.api_v1.endpoints'
    ]
    
    for logger_name in loggers:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.DEBUG)
        # Ensure propagation is enabled
        logger.propagate = True
        # Remove any existing handlers
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
    
    # Log a test message to verify configuration
    logging.debug("Logging system initialized with DEBUG level")