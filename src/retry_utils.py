import time
from functools import wraps
from google.api_core.exceptions import ResourceExhausted

def retry_with_backoff(max_retries=10, initial_delay=10, backoff_factor=1.5):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            for i in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    error_str = str(e).lower()
                    if "429" in error_str or "resource_exhausted" in error_str or "quota exceeded" in error_str:
                        if i == max_retries - 1:
                            raise
                        print(f"Rate limit hit. Retrying in {delay} seconds...")
                        time.sleep(delay)
                        delay *= backoff_factor
                    else:
                        raise
        return wrapper
    return decorator
