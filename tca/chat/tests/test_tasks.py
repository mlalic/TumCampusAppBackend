"""
Module with tests for celery tasks found in :mod:`chat.tasks`.
"""

from django.test import TestCase

from .factories import MemberFactory
from .factories import MessageFactory
from .factories import ChatRoomFactory

from chat.tasks import send_message_notifications

import mock


@mock.patch('chat.tasks.get_notifiers')
class SendMessageNotificationsTaskTestCase(TestCase):
    """
    Tests for the :func:`chat.tasks.send_message_notifications` task.
    """
    def setUp(self):
        MemberFactory.create_batch(5)
        ChatRoomFactory.create_batch(5)
        self.message = MessageFactory.create()
        self.mock_notifiers = [
            mock.MagicMock(),
            mock.MagicMock(),
        ]

    def set_up_mock_notifiers(self, mock_get_notifiers):
        mock_get_notifiers.return_value = self.mock_notifiers

    def test_send_notifications_existing_message(self, mock_get_notifiers):
        """
        Tests that all notifiers are correctly notified when the task runs.
        """
        self.set_up_mock_notifiers(mock_get_notifiers)

        send_message_notifications(self.message.pk)

        mock_get_notifiers.assert_called_once_with()
        # Each notifer was called once with the correct message instance
        for mock_notifier in self.mock_notifiers:
            mock_notifier.notify.assert_called_once_with(self.message)

    def test_invalid_message_pk(self, mock_get_notifiers):
        """
        Tests that when the task receives a message id which does not
        exist, no notifiers are notified of anything.
        """
        self.set_up_mock_notifiers(mock_get_notifiers)

        # Initiate the task with a non existent message PK
        send_message_notifications(self.message.pk + 5)

        # None of the notifiers were notified
        for mock_notifier in self.mock_notifiers:
            self.assertFalse(mock_notifier.notify.called)
