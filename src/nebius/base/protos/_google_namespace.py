"""Restore the shared Google package namespace for split Bazel wheels."""

from pkgutil import extend_path

import google

# Some protobuf wheels still ship an empty ``google/__init__.py``. Bazel keeps
# distributions in separate import roots instead of merging site-packages, so
# make modules supplied by the other Google distributions visible explicitly.
google.__path__ = extend_path(google.__path__, google.__name__)
