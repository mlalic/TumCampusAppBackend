"""
Hooks for the :mod:`chat` app.
"""

from django.conf import settings

from chat.tasks import send_message_notifications
from chat.tasks import send_confirmation_email


def validate_message_signature(message):
    """
    A hook function which triggers the validation of the given
    :class:`chat.models.Message` instance.
    """
    if message.validate_signature():
        send_message_notifications.delay(message.pk)


def confirm_new_key(public_key):
    """
    A hook function which triggers the email confirmation of a new public
    key -- if enabled.
    """
    if settings.TCA_ENABLE_EMAIL_CONFIRMATIONS:
        send_confirmation_email.delay(public_key.pk)
    elif settings.DEBUG:
        # Only if the app is in DEBUG mode should the key be automatically
        # enabled. In production it is never done.
        public_key.active = True
        public_key.save()
