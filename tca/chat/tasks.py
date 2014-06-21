"""
Celery tasks for the :mod:`chat` app of the TCA Backend.
"""
from __future__ import absolute_import

from django.template.loader import render_to_string
from django.core import mail
from django.conf import settings

from celery import shared_task

from chat.models import Message
from chat.models import PublicKey
from chat.models import PublicKeyConfirmation

from chat.notifiers import get_notifiers

from urlparse import urlunsplit


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


def _build_url(url_path):
    """
    Function builds an absolute URL for the given url path.
    """
    return urlunsplit((
        settings.TCA_SCHEME,
        settings.TCA_DOMAIN_NAME,
        url_path,
        '',
        ''
    ))
    

@shared_task
def send_confirmation_email(public_key_id):
    """
    A Celery task which generates a confirmation email for the given
    public key and sends it to the member's LRZ email address.
    """
    try:
        public_key = PublicKey.objects.get(pk=public_key_id)
    except PublicKey.DoesNotExist:
        return

    # Creates a new confirmation instance
    confirmation = PublicKeyConfirmation.objects.create(
        public_key=public_key)

    # Send an email to the user

    # Build the absolute URL for the confirmation
    confirmation_url = _build_url(confirmation.get_absolute_url())
    # Render the email
    email_body = render_to_string('confirmation-email.txt', {
        'confirmation_url': confirmation_url,
        'confirmation': confirmation,
    })

    # Send it
    mail.send_mail(
        '[TCA] Confirm New Public Key',
        email_body,
        settings.TCA_FROM_EMAIL,
        [public_key.member.lrz_email]
    )
