from django.core.management.base import (
    BaseCommand,
    CommandError,
)

from chat.models import Message

from django.utils import timezone
from django.conf import settings

from datetime import timedelta


class Command(BaseCommand):
    help = 'Removes any expired messages from the server'

    def log(self, text):
        """
        Log the given text to the console output.
        """
        self.stdout.write(text)

    def handle(self, *args, **kwargs):
        delta = timedelta(days=settings.TCA_MESSAGE_EXPIRATION_DAYS)
        qs = Message.objects.filter(timestamp__lte=timezone.now() - delta)

        # Keep the count of the messages in order to display a status
        # message later on
        count = qs.count()

        qs.delete()

        self.log("Deleted {count} expired messages".format(
            count=count))
