"""
Settings for the TUM Campus App Backend Django project.
"""
from .defaults import *

try:
    from local_settings import *
except ImportError:
    pass

# Some settings can be calculated based on other values.
# However, if the value has already been set by local_settings directly,
# do not override it with the calculated value.
if 'TCA_FROM_EMAIL' not in globals():
    TCA_FROM_EMAIL = 'noreply@' + TCA_DOMAIN_NAME
