"""
Celery tasks for the :mod:`chat` app of the TCA Backend.
"""
from __future__ import absolute_import

from celery import shared_task

from chat.models import Message
from chat.notifiers import get_notifiers


@shared_task
def send_message_notifications(message_id):
    """
    Celery task which sends a notification that a new message has been
    posted. It simply notifies all notifiers defined in :mod:`chat.notifiers`
    and passes them the corresponding :class:`chat.models.Message` instance.

    :param message_id: The ID of the message for which the notifications
        should be sent. The task takes an ID, not a full
        :class:`chat.models.Message` instance because it is possible that the
        instance gets deleted from the database in the mean time.
    """
    try:
        message = Message.objects.get(pk=message_id)
    except Message.DoesNotExist:
        # The message somehow disappeared in the mean time
        return

    # Alert all notifiers (observers)
    for notifier in get_notifiers():
        notifier.notify(message)
