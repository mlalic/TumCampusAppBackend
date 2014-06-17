"""
Hooks for the :mod:`chat` app.
"""

def validate_message_signature(message):
    """
    A hook function which triggers the validation of the given
    :class:`chat.models.Message` instance.
    """
    message.validate_signature()
