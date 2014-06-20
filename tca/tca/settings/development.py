"""
Default settings for a development environment.

Major differences to a production environment:

    - Celery tasks always run synchronously
    - GCM notifications are disabled

If it is necessary to override any of these settings for development
purposes (such as integration testing), directly edit this file.
"""

#: In development set celery to execute tasks synchronously
CELERY_ALWAYS_EAGER = True
#: Disable GCM notifications in development
TCA_ENABLE_GCM_NOTIFICATIONS = False
