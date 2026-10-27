import time
from functools import wraps


def ttl_cache(seconds):
    """Remember a function's results for a number of seconds, keyed by its arguments.

    Results of None are not remembered, so a failed download is retried next time.
    """

    def decorator(func):
        store = {}

        @wraps(func)
        def wrapper(*args):
            now = time.time()
            saved = store.get(args)
            if saved is not None and now - saved[0] < seconds:
                return saved[1]
            value = func(*args)
            if value is not None:
                store[args] = (now, value)
            return value

        wrapper.clear = store.clear
        return wrapper

    return decorator