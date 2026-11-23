"""Compatibility module for the original backend layout."""
import sys
from app import db as _db

sys.modules[__name__] = _db
