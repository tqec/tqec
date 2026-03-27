import importlib.metadata

try:
    __version__ = importlib.metadata.version("tqec")
except importlib.metadata.PackageNotFoundError:
    # Fix: allow running from source tree without an installed distribution.
    __version__ = "0.0.0"
