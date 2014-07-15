"""
Tests for the :mod:`chat` app-specific management commands.
"""
from django.test import TestCase
from django.test.utils import override_settings

from django.core.management import call_command
from django.utils import timezone

import datetime

from chat.models import Message

from .factories import MemberFactory
from .factories import MessageFactory
from .factories import ChatRoomFactory

import mock


class DeleteStaleMessagesTestCase(TestCase):
    """
    Tests for the ``clean_expired_messages`` management command.
    """
    def setUp(self):
        MemberFactory.create_batch(10)
        ChatRoomFactory.create_batch(5)
        self.real_now = timezone.now()

    def offset_now(self, delta):
        """
        Helper method offsets the current time by the given delta.
        """
        timezone.now.return_value = self.real_now + delta

    @override_settings(TCA_MESSAGE_EXPIRATION_DAYS=5)
    @mock.patch('chat.management.commands.clean_expired_messages.Command.log')
    @mock.patch('chat.management.commands.clean_expired_messages.timezone.now')
    def test_old_messages_deleted(self, mock_now, mock_stdout):
        """
        Tests that messages older than the expiration days are deleted
        whereas the ones newer than that are not touched.
        """
        # Create messages newer than the expiration
        mock_now.return_value = self.real_now
        new_messages = MessageFactory.create_batch(5)
        # Create messages older than the expiration
        self.offset_now(datetime.timedelta(days=-5, seconds=-5))
        older_messages = MessageFactory.create_batch(10)
        # Restore the current time before running the management command
        mock_now.return_value = self.real_now

        call_command('clean_expired_messages')

        all_messages = Message.objects.all()
        # Only the new messages left in the system?
        self.assertEquals(len(new_messages), all_messages.count())
        for msg in new_messages:
            self.assertIn(msg, all_messages)
        # The correct status output was generated
        mock_stdout.assert_called_once_with(
            "Deleted {count} expired messages".format(
                count=len(older_messages)))
