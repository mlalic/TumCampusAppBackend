"""
Default settings for a development environment.

Major differences to a production environment:

    - Celery tasks always run synchronously
    - GCM notifications are disabled
    - Emails confirming public keys are not sent

If it is necessary to override any of these settings for development
purposes (such as integration testing), directly edit this file.
"""

#: In development set celery to execute tasks synchronously
CELERY_ALWAYS_EAGER = True
#: Disable GCM notifications in development
TCA_ENABLE_GCM_NOTIFICATIONS = False

#: In development the emails are dumped to the console instead of actually
#: sending them out.
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

TCA_SCHEME = 'http'
TCA_DOMAIN_NAME = 'localhost:8888'
