"""
Logging decorators for filebunny operations.

Verbosity can be controlled via environment variables:
- `FILEBUNNY_LOG_LEVEL` (preferred): DEBUG, INFO, WARNING, ERROR, CRITICAL
- `FILEBUNNY_VERBOSE` (legacy): when set to "1", uses INFO; otherwise WARNING.
"""

import logging
import time
from functools import wraps
import sys
import os

# Initialize logging level based on environment
_level_name = os.environ.get("FILEBUNNY_LOG_LEVEL")
if _level_name:
    _level = getattr(logging, _level_name.upper(), logging.INFO)
else:
    _verbose = os.environ.get("FILEBUNNY_VERBOSE") == "1"
    _level = logging.INFO if _verbose else logging.WARNING
logging.basicConfig(
    level=_level,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stderr,
)

def log_call(fn):
    """Log function calls with arguments"""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        logging.info("CALL %s args=%s kwargs=%s", fn.__name__, args[1:], kwargs)
        return fn(*args, **kwargs)
    return wrapper

def log_timing(fn):
    """Log function execution time"""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        try:
            return fn(*args, **kwargs)
        finally:
            elapsed = (time.perf_counter() - start) * 1000
            logging.info("TIME %s: %.2f ms", fn.__name__, elapsed)
    return wrapper

def log_errors(fn):
    """Log function errors"""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            logging.error("ERROR in %s: %s", fn.__name__, e)
            raise
    return wrapper
