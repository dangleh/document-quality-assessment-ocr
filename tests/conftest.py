import pytest
from unittest.mock import patch
from concurrent.futures import Future

# A mock executor that runs tasks synchronously in the main thread.
# This mimics the interface of ProcessPoolExecutor but avoids actual multiprocessing.
class SyncExecutor:
    def __init__(self, max_workers=None):
        # max_workers is ignored as we are running synchronously.
        pass

    def submit(self, fn, *args, **kwargs):
        """Executes the function immediately and returns a completed Future."""
        future = Future()
        try:
            result = fn(*args, **kwargs)
            future.set_result(result)
        except Exception as e:
            future.set_exception(e)
        return future

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        pass

@pytest.fixture(autouse=True)
def disable_multiprocessing_for_tests(monkeypatch):
    """
    Fixture to automatically replace ProcessPoolExecutor with a synchronous
    executor for all tests. This prevents tests from hanging due to
    multiprocessing issues with pytest-cov and ensures deterministic,
    sequential execution during testing.
    """
    # Use monkeypatch to replace the class in the specified module
    monkeypatch.setattr("document_assessor.evaluator.ProcessPoolExecutor", SyncExecutor)
