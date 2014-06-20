"""
Hooks for the :mod:`chat` app.
"""

from chat.tasks import send_message_notifications

def validate_message_signature(message):
    """
    A hook function which triggers the validation of the given
    :class:`chat.models.Message` instance.
    """
    if message.validate_signature():
        send_message_notifications.delay(message.pk)
