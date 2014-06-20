"""
Settings for the TUM Campus App Backend Django project.
"""
from .defaults import *

try:
    from local_settings import *
except ImportError:
    pass
