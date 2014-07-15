"""
Tests for the :mod:`chat.notifiers` module classes.
"""

from django.test import TestCase
from django.test.utils import override_settings

import mock

from chat.notifiers import GcmNotifier
from chat.hooks import validate_message_signature

from .factories import MemberFactory
from .factories import MessageFactory
from .factories import ChatRoomFactory


@mock.patch('chat.notifiers.GCM')
class GcmNotifierTestCase(TestCase):
    """
    Tests that the :class:`chat.notifiers.GcmNotifier` performs the correct
    notification.
    """

    def _set_registration_id(self, member):
        """
        Helper method which helps set up a member with a dummy registration
        ID.
        """
        member.registration_ids = [member.lrz_id]
        member.save()

    def setUp(self):
        self.members = MemberFactory.create_batch(5)
        # Give each member a unique dummy registration ID
        for member in self.members:
            self._set_registration_id(member)

        self.sender = MemberFactory.create()

        self.chat_rooms = ChatRoomFactory.create_batch(2)
        self.target_chat_room = self.chat_rooms[0]

        self.api_key = 'dummy-api-key'

    def get_registration_ids(self, members):
        """
        Helper method returning the registration IDs of the given members
        """
        reg_ids = []
        for member in members:
            reg_ids.extend(member.registration_ids)

        return reg_ids

    def set_up_notifier(self):
        self.notifier = GcmNotifier(self.api_key)

    def test_set_up(self, gcm_mock):
        """
        Test that instantiating a notifier performs the correct
        initialization of the GCM service.
        """
        self.set_up_notifier()

        # The GCM service was initialized with the correct API key
        gcm_mock.assert_called_once_with(self.api_key)

    def assert_data_correct(self, data, message):
        """
        Helper assertion method checking whether the given ``data``
        dictionary correctly represents the given ``message``
        """
        fields = (
            'timestamp',
            'url',
            'text',
            'member',
            'valid',
            'signature',
            'id',
        )
        self.assertEquals(len(fields), len(data.items()))

        self.assertTrue(data['url'].endswith(message.get_absolute_url()))
        self.assertTrue(data['member']['url'].endswith(
            message.member.get_absolute_url()))
        self.assertEquals(data['member']['lrz_id'], message.member.lrz_id)
        self.assertEquals(data['text'], message.text)
        self.assertEquals(data['valid'], message.valid)
        self.assertEquals(data['signature'], message.signature)

    def test_notification_sent(self, gcm_mock):
        """
        Tests that the notification is correctly sent to all members of
        the chat room to which a message is posted.
        """
        self.set_up_notifier()
        # Join a part of the members to the chat room
        # - the sender has got to be a part of it
        self.target_chat_room.members.add(self.sender)
        # - A subset of existing members too
        for member in self.members[:3]:
            self.target_chat_room.members.add(member)
        # Set up a message in the chat room
        message = MessageFactory.create(
            chat_room=self.target_chat_room,
            member=self.sender)

        self.notifier.notify(message)

        gcm_mock_instance = gcm_mock()
        self.assertTrue(gcm_mock_instance.json_request.called)
        # Check the parameters of the call
        args, kwargs = gcm_mock_instance.json_request.call_args
        # No positional arguments
        self.assertEquals(0, len(args))
        # Exactly 2 kwargs
        self.assertEqual(2, len(kwargs.items()))
        self.assertIn('registration_ids', kwargs)
        self.assertIn('data', kwargs)
        # Correct values for them?
        # - registration IDs
        expected_ids = self.get_registration_ids(self.members[:3])
        self.assertListEqual(expected_ids, kwargs['registration_ids'])
        # - data
        self.assert_data_correct(kwargs['data'], message)

    def test_no_notification_empty_chat_room(self, gcm_mock):
        """
        Tests that there is no notification sent when there is only a
        single member in the chat room (the one that sent the request)
        """
        self.set_up_notifier()
        # Join a part of the members to the chat room
        # - the sender has got to be a part of it
        self.target_chat_room.members.add(self.sender)
        # Set up a message in the chat room
        message = MessageFactory.create(
            chat_room=self.target_chat_room,
            member=self.sender)

        self.notifier.notify(message)

        gcm_mock_instance = gcm_mock()
        # No calls to the GCM service
        self.assertFalse(gcm_mock_instance.json_request.called)

    @override_settings(TCA_ENABLE_GCM_NOTIFICATIONS=False)
    def test_gcm_notifier_disabled(self, gcm_mock):
        """
        Tests that setting the corresponding setting value disables
        GCM notifications.
        """
        self.assertFalse(GcmNotifier.is_enabled())

    @override_settings(TCA_ENABLE_GCM_NOTIFICATIONS=True)
    def test_gcm_notifier_enable(self, gcm_mock):
        """
        Tests that setting the corresponding setting value enables
        GCM notifications.
        """
        self.assertTrue(GcmNotifier.is_enabled())

    @override_settings(TCA_GCM_API_KEY='override-settings-dummy-api-key')
    def test_gcm_notifier_get_instance(self, gcm_mock):
        """
        Tests that the classmethod
        :classmeth:`chat.notifiers.GcmNotifier.get_instance`
        returns constructs the correct GCM notifier.
        """
        notifier = GcmNotifier.get_instance()

        gcm_mock.assert_called_once_with('override-settings-dummy-api-key')


@mock.patch('chat.hooks.send_message_notifications')
class ValidateMessageHookTestCase(TestCase):
    """
    Tests that the :func:`chat.tasks.send_message_notifications` task is
    initiated after message validation.
    """
    def setUp(self):
        # A mock message which will be passed to the function-under-test
        self.message = mock.MagicMock()
        self.mock_pk = 5
        self.message.pk = self.mock_pk

    def set_message_signature_validity(self, valid):
        """
        Helper method sets the validty of the mock message passed to the
        :func:`chat.hooks.validate_message_signature` function.
        """
        self.message.validate_signature.return_value = valid

    def test_valid_signature(self, mock_send_notifications):
        """
        Tests that when a message is found to be valid, the notification
        is initiated.
        """
        self.set_message_signature_validity(True)

        validate_message_signature(self.message)

        mock_send_notifications.delay.assert_called_once_with(self.mock_pk)

    def test_invalid_signature(self, mock_send_notifications):
        """
        Tests that when a message is found to be invalid, there is no
        notification initiated.
        """
        self.set_message_signature_validity(False)

        validate_message_signature(self.message)

        self.assertFalse(mock_send_notifications.delay.called)
