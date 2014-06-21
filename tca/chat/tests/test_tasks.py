"""
Module with tests for celery tasks found in :mod:`chat.tasks`.
"""

from django.test import TestCase
from django.test.utils import override_settings

from django.core import mail

from .factories import MemberFactory
from .factories import MessageFactory
from .factories import ChatRoomFactory
from .factories import PublicKeyFactory

from chat.models import PublicKeyConfirmation

from chat.tasks import send_message_notifications
from chat.tasks import send_confirmation_email

from chat.hooks import confirm_new_key

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


class EmailConfirmationTaskTestCase(TestCase):
    """
    Tests for the :func:`chat.tasks.send_confirmation_email` task.
    """
    def setUp(self):
        self.member = MemberFactory.create_batch(5)[0]
        self.public_key = PublicKeyFactory.create(member=self.member)

    @override_settings(
        TCA_SCHEME='http',
        TCA_DOMAIN_NAME='dummy.com',
        TCA_FROM_EMAIL='dummy-from@dummy')
    def test_send_email(self):
        """
        Tests that an email is sent when the public key exists
        """
        send_confirmation_email(self.public_key.pk)

        # Confirmation generated
        self.assertEquals(1, PublicKeyConfirmation.objects.count())
        conf = PublicKeyConfirmation.objects.all()[0]
        # Associated to the public key?
        self.assertEquals(self.public_key.pk, conf.public_key.pk)
        # PK still inactive?
        self.assertFalse(self.public_key.active)

        # Email sent
        self.assertEqual(1, len(mail.outbox))
        # Email contains the URL to the confirmation
        msg = mail.outbox[0]
        self.assertIn(conf.get_absolute_url(), msg.body)
        # Sent to the correct user
        self.assertEquals(1, len(msg.to))
        self.assertEquals(self.member.lrz_email, msg.to[0])
        # Correct From header?
        self.assertEquals('dummy-from@dummy', msg.from_email)

    def test_public_key_does_not_exist(self):
        """
        Tests that no emails are sent when the public key does not exist
        """
        send_confirmation_email(self.public_key.pk + 5)

        # No emails sent
        self.assertEquals(0, len(mail.outbox))
        # No confirmations created
        self.assertEquals(0, PublicKeyConfirmation.objects.count())

    @override_settings(TCA_ENABLE_EMAIL_CONFIRMATIONS=True)
    @mock.patch('chat.hooks.send_confirmation_email')
    def test_hook_initiates_send_mail(self, mock_send_confirmation):
        """
        Tests that the :func:`chat.hooks.confirm_new_key` initiates the
        task.
        """
        public_key = mock.MagicMock()
        public_key.pk = 5

        confirm_new_key(public_key)

        mock_send_confirmation.delay.assert_called_once_with(public_key.pk)

    @override_settings(
        TCA_ENABLE_EMAIL_CONFIRMATIONS=False,
        DEBUG=False)
    @mock.patch('chat.hooks.send_confirmation_email')
    def test_hook_does_not_send(self, mock_send_confirmation):
        """
        Tests that the :func:`chat.hooks.confirm_new_key` does not initiate
        the task when disabled in the settings.
        """
        public_key = mock.MagicMock()
        public_key.pk = 5

        confirm_new_key(public_key)

        self.assertFalse(mock_send_confirmation.delay.called)
