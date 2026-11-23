"""Compatibility module for the original backend layout."""
import sys
from app import graph_engine as _graph_engine

sys.modules[__name__] = _graph_engine
