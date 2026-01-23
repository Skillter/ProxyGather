"""
Graceful termination handler for ProxyGather scripts.
Provides reliable Ctrl+C handling with proper cleanup of resources.
"""

import signal
import sys
import threading
import os
from typing import Callable, Optional, Set
from contextlib import contextmanager

class TerminationHandler:
    """
    Global termination handler that coordinates graceful shutdown.

    Features:
    - Handles SIGINT (Ctrl+C) and SIGTERM
    - Thread-safe state management
    - Callback registration for cleanup
    - Prevents duplicate signal handlers
    - Supports forced exit on multiple signals
    """

    def __init__(self):
        self._terminating = False
        self._lock = threading.Lock()
        self._callbacks: Set[Callable] = set()
        self._original_handlers: dict = {}
        self._signals_registered = False
        self._kill_counter = 0

    @property
    def is_terminating(self) -> bool:
        """Check if termination has been requested."""
        with self._lock:
            return self._terminating

    def request_termination(self, signum=None, frame=None):
        """Request graceful termination. Called by signal handlers."""
        with self._lock:
            self._kill_counter += 1
            if self._terminating:
                remaining = 3 - self._kill_counter
                if remaining <= 0:
                    print(f"\n[CRITICAL] Forced termination requested ({self._kill_counter}/3). Exiting immediately.")
                    # Use os._exit to bypass SystemExit handlers and cleanup, ensuring immediate exit
                    os._exit(1)
                else:
                    print(f"\n[INFO] Termination in progress. Press Ctrl+C {remaining} more times to force quit.")
                return
            self._terminating = True

        signal_name = signal.Signals(signum).name if signum else "manual"
        print(f"\n\n[INTERRUPTED] Termination signal received ({signal_name}). Cleaning up... (Press Ctrl+C 2 more times to force kill)")

        # Run all registered callbacks
        for callback in list(self._callbacks):
            try:
                callback()
            except Exception as e:
                print(f"\n[ERROR] Cleanup callback failed: {e}")

    def register_callback(self, callback: Callable):
        """Register a cleanup callback to run on termination."""
        self._callbacks.add(callback)

    def unregister_callback(self, callback: Callable):
        """Unregister a cleanup callback."""
        self._callbacks.discard(callback)

    def register_signals(self):
        """Register signal handlers for SIGINT and SIGTERM."""
        if self._signals_registered:
            return

        self._original_handlers[signal.SIGINT] = signal.signal(signal.SIGINT, self.request_termination)

        # SIGTERM is available on Unix-like systems only
        if hasattr(signal, 'SIGTERM'):
            self._original_handlers[signal.SIGTERM] = signal.signal(signal.SIGTERM, self.request_termination)

        self._signals_registered = True

    def restore_signals(self):
        """Restore original signal handlers."""
        for sig, handler in self._original_handlers.items():
            signal.signal(sig, handler)
        self._signals_registered = False

    def check_exit(self):
        """Check if termination was requested and exit if so."""
        if self.is_terminating:
            sys.exit(130)  # Standard exit code for SIGINT


# Global instance
_global_handler: Optional[TerminationHandler] = None


def get_termination_handler() -> TerminationHandler:
    """Get or create the global termination handler."""
    global _global_handler
    if _global_handler is None:
        _global_handler = TerminationHandler()
    return _global_handler


@contextmanager
def termination_context(callbacks: Optional[list] = None):
    """
    Context manager for automatic signal handling and cleanup.

    Args:
        callbacks: Optional list of cleanup callbacks to register

    Example:
        with termination_context([cleanup_func]):
            do_work()
    """
    handler = get_termination_handler()

    if callbacks:
        for callback in callbacks:
            handler.register_callback(callback)

    handler.register_signals()

    try:
        yield handler
    finally:
        handler.restore_signals()
        if callbacks:
            for callback in callbacks:
                handler.unregister_callback(callback)


def should_terminate() -> bool:
    """Convenience function to check if termination was requested."""
    return get_termination_handler().is_terminating


def request_termination(signum=None, frame=None):
    """Convenience function to request termination."""
    get_termination_handler().request_termination(signum, frame)


def check_terminate_exit():
    """Convenience function to check and exit if termination was requested."""
    get_termination_handler().check_exit()
