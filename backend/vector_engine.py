"""Compatibility module for the original backend layout."""
import sys
from app import vector_engine as _vector_engine

sys.modules[__name__] = _vector_engine
