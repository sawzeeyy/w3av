"""
Configuration loading for URL extraction.

Handles MIME types and custom file extensions.
"""
import importlib.resources
from functools import lru_cache

# Global variable to store custom file extensions for the current extraction
_custom_file_extensions = set()


def get_custom_extensions():
    """Return the current custom file extensions."""
    return _custom_file_extensions


def set_custom_extensions(extensions):
    """
    Set custom file extensions.

    Parameters:
    - extensions: Comma-separated string of extensions or a set of extensions
    """
    global _custom_file_extensions
    _custom_file_extensions = set()

    if isinstance(extensions, set):
        _custom_file_extensions = extensions
    elif extensions:
        for ext in extensions.split(','):
            ext = ext.strip()
            if ext:
                # Normalize: remove dot prefix if present, then lowercase
                if ext.startswith('.'):
                    ext = ext[1:]
                _custom_file_extensions.add(ext.lower())


@lru_cache(maxsize=1)
def load_mime_types():
    """
    Load MIME types from config files (cached after first call).

    Returns:
        frozenset of MIME type strings (~2007 types)

    Config Files:
        - sawari/config/iana_mimetypes.txt (1994 official IANA MIME types)
        - sawari/config/mimetypes.txt (13 additional non-standard MIME types)
    """
    mime_types = set()

    # Load IANA official MIME types
    with importlib.resources.files('sawari.config').joinpath('iana_mimetypes.txt')\
            .open('r') as file:
        mime_types.update(line.strip() for line in file if line.strip())

    # Load additional non-standard MIME types
    with importlib.resources.files('sawari.config').joinpath('mimetypes.txt')\
            .open('r') as file:
        mime_types.update(line.strip() for line in file if line.strip())

    return frozenset(mime_types)  # frozenset for immutability and hashability
