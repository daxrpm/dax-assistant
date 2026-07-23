"""Dax Assistant — Voice-first personal AI assistant."""

from importlib.metadata import PackageNotFoundError, version

try:
    # Read the version the package was actually built with, so an installed
    # release can never disagree with its own metadata. A hardcoded literal here
    # silently went stale and made the backend log 0.1.0 while running 0.2.0.
    __version__ = version("dax-assistant")
except PackageNotFoundError:  # running from a source tree that was never built
    __version__ = "0.0.0+unknown"
