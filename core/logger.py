import logging
import sys
import os
from datetime import datetime

def setup_logger(name: str = "Sentinel"):
    """Configures a unified logger with console and file output."""
    logger = logging.getLogger() # Configure the root logger
    logger.setLevel(logging.INFO)

    # Prevent double formatting if logger already exists
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File Handler
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        
    log_file = os.path.join(log_dir, f"sentinel_{datetime.now().strftime('%Y%m%d')}.log")
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger

# Convenience instance
log = setup_logger()
stone_logger = log # Alias for easy transition
