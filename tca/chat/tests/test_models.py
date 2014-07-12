"""
Tests for :mod:`chat` app models.
"""

from django.test import TestCase
from django.test.utils import override_settings

from django.utils import timezone

from chat.models import Member
from chat.models import Message
from chat.models import SystemMessage
from chat.models import ChatRoom
from chat.models import PublicKey
from chat.models import PublicKeyConfirmation

from .factories import MemberFactory
from .factories import MessageFactory
from .factories import ChatRoomFactory
from .factories import PublicKeyFactory

import os
import json
import mock
import datetime


class MessageSignatureValidationTestCase(TestCase):
    """
    Tests for the :class:`chat.models.Message` model regarding signature
    validation.
    """
    @classmethod
    def get_fixture_path(cls, fixture_file_name):
        """Returns the path to a fixture files for this TestCase."""
        base_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(
            base_dir,
            'fixtures',
            fixture_file_name)

    def _load_pubkey(self):
        with open(self.get_fixture_path('pubkey.pub'), 'rb') as pubkey_file:
            data = pubkey_file.read()
        # Make sure the public key is unicode too
        return data.decode('utf-8')

    def setUp(self):
        # Set up a member with an associated pubkey
        self.member = MemberFactory.create()
        # Use a real pubkey for the fixture
        self.public_key = PublicKeyFactory.create(
            member=self.member,
            key_text=self._load_pubkey(),
            active=True)
        # Set up a chat room to which messages could be posted
        ChatRoomFactory.create()
        # Load the message fixtures too
        with open(self.get_fixture_path('message_fixtures.json')) as f:
            self.message_fixtures = json.load(f)

    def create_from_fixture(self, fixture_name, member=None):
        """
        Helper method creating a :class:`chat.models.Message` instance
        based on a fixture name.
        """
        kwargs = {}
        if member is not None:
            kwargs['member'] = member

        fixture = self.message_fixtures[fixture_name]
        kwargs['text'] = fixture['text']
        kwargs['signature'] = fixture['signature']

        return MessageFactory.create(**kwargs)

    def test_validate_signature_simple(self):
        """
        Test that a simple signature can be validated.
        """
        message = self.create_from_fixture('simple-message')
        # Sanity check -- the message is not valid in the beginning
        self.assertFalse(message.valid)

        result = message.validate_signature()

        self.assertTrue(result)
        self.assertTrue(message.valid_signature)
        # Reload the message from the DB to make sure the valid status
        # got saved
        message = Message.objects.get(pk=message.pk)
        self.assertTrue(message.valid)

    def test_validate_signature_unicode(self):
        """
        Tests that a signature of a unicode text can be validated.
        """
        message = self.create_from_fixture('unicode-korean')
        # Sanity check -- the message is not valid in the beginning
        self.assertFalse(message.valid)

        result = message.validate_signature()

        self.assertTrue(result)
        self.assertTrue(message.valid_signature)
        # Reload the message from the DB to make sure the valid status
        # got saved
        message = Message.objects.get(pk=message.pk)
        self.assertTrue(message.valid)

    def test_validate_signature_invalid_user(self):
        """
        Tests that when a signature does not match the public key of the
        member who posted it, there is no change to the message validity
        (i.e. it stays False).
        """
        new_member = MemberFactory.create()
        message = self.create_from_fixture('simple-message', member=new_member)
        # Sanity check -- the message is not valid in the beginning
        self.assertFalse(message.valid)

        result = message.validate_signature()

        self.assertFalse(result)
        self.assertFalse(message.valid_signature)
        # Reload the message from the DB to make sure the valid status
        # did not change
        message = Message.objects.get(pk=message.pk)
        self.assertFalse(message.valid)

    def test_validate_signature_invalid(self):
        """
        Tests when the signature is invalid (does not match the message
        and the public key), the validity of the message stays False.
        """
        fixture = self.message_fixtures['simple-message']
        message = MessageFactory.create(
                text=fixture['text'],
                signature='asdf')

        result = message.validate_signature()

        self.assertFalse(result)
        self.assertFalse(message.valid_signature)
        # Reload the message from the DB to make sure the valid status
        # did not change
        message = Message.objects.get(pk=message.pk)
        self.assertFalse(message.valid)

    def test_validate_signature_inactive(self):
        """
        Tests that when validating a signature inactive public keys
        are ignored.
        """
        # Deactivate the key
        self.public_key.active = False
        self.public_key.save()
        fixture = self.message_fixtures['simple-message']
        message = MessageFactory.create(
                text=fixture['text'],
                signature=fixture['signature'])

        result = message.validate_signature()

        self.assertFalse(result)
        self.assertFalse(message.valid_signature)
        # Reload the message from the DB to make sure the valid status
        # did not change
        message = Message.objects.get(pk=message.pk)
        self.assertFalse(message.valid)


class MemberTestCase(TestCase):
    def setUp(self):
        self.member = MemberFactory.create()

    def test_lrz_email(self):
        """
        Test that a member's email derived from the LRZ ID is correctly
        generated.
        """
        expected = self.member.lrz_id + "@mytum.de"

        self.assertEquals(expected, self.member.lrz_email)


class PublicKeyConfirmationTestCase(TestCase):
    def setUp(self):
        self.member = MemberFactory.create_batch(5)[0]
        self.pk = PublicKeyFactory.create(member=self.member)
        self.confirmation = PublicKeyConfirmation.objects.create(
            public_key=self.pk)

    def offset_now(self, delta):
        """
        Helper method offsets the current time by the given delta.
        """
        timezone.now.return_value = self.confirmation.created + delta

    @override_settings(TCA_CONFIRMATION_EXPIRATION_HOURS=2)
    @mock.patch('chat.models.timezone.now')
    def test_expired_confirmation(self, mock_now):
        """
        Tests that a confirmation correctly expires after the time
        given in the settings.
        """
        # Set the current time to the future when the confirmation
        # should be expired
        self.offset_now(datetime.timedelta(hours=2, seconds=1))

        self.assertTrue(self.confirmation.is_expired())

    @override_settings(TCA_CONFIRMATION_EXPIRATION_HOURS=2)
    @mock.patch('chat.models.timezone.now')
    def test_not_expired_confirmation(self, mock_now):
        """
        Tests that a confirmation is not considered expired before the
        time given in the settings.
        """
        # Set the current time to the future, but not enough that the
        # key expires
        self.offset_now(datetime.timedelta(hours=1))

        self.assertFalse(self.confirmation.is_expired())

    @override_settings(TCA_CONFIRMATION_EXPIRATION_HOURS=2)
    @mock.patch('chat.models.timezone.now')
    def test_expired_edge(self, mock_now):
        """
        Tests the confirmation validity at the edges of the expiration
        time period given in the settings.
        """
        # Just before the time in the settings
        self.offset_now(
            datetime.timedelta(hours=2, seconds=-1))
        self.assertFalse(self.confirmation.is_expired())

        # At the exact edge -- not expired yet!
        self.offset_now(datetime.timedelta(hours=2))
        self.assertFalse(self.confirmation.is_expired())

        # Just after the edge -- expired
        self.offset_now(datetime.timedelta(hours=2, seconds=1))
        self.assertTrue(self.confirmation.is_expired())


class SystemMessageTestCase(TestCase):
    """
    Tests for the :class:`chat.models.SystemMessage` model.
    """
    def setUp(self):
        self.chat_room = ChatRoomFactory()

    def set_up_system_message(self, text=None, auto_save=False):
        """
        Helper method which returns a :class:`chat.models.SystemMessage`
        instance.

        :param text: The text of the message to be created.
            If the ``text`` parameter is not provided, a placeholder text
            is used instead.

        :param auto_save: A boolean indicating whether the message should
            already be saved by the method.
        """
        if text is None:
            text = "System message text"

        message = SystemMessage(text=text, chat_room=self.chat_room)
        if auto_save:
            message.save()

        return message

    def test_get_bot_user(self):
        """
        Tests the ``get_bot_user`` method creates a bot user
        """
        bot = SystemMessage.get_bot_user()

        self.assertEquals("Bot", bot.display_name)
        self.assertEquals("bot", bot.lrz_id)
        self.assertEquals(1, Member.objects.count())

    def test_bot_user_auto_created(self):
        """
        Tests that the bot user is automatically created when it doesn't
        already exist prior to creating a :class:`chat.models.SystemMessage`
        """
        # Sanity check -- the bot does not exist
        self.assertEquals(0, Member.objects.count())

        self.set_up_system_message(auto_save=True)

        # The bot now exists?
        self.assertEquals(1, Member.objects.count())
        bot = Member.objects.all()[0]
        self.assertEquals("Bot", bot.display_name)
        # It is also the same object as returned by the get_bot_user?
        self.assertEquals(SystemMessage.get_bot_user(), bot)

    def test_system_message_auto_valid(self):
        """
        Tests that a :class:`chat.models.SystemMessage` is always created
        as a valid message.
        """
        msg = self.set_up_system_message()

        # The message is valid before even saving it?
        self.assertTrue(msg.valid)

    def test_system_message_valid_on_save(self):
        """
        Tests that a :class:`chat.models.SystemMessage` is valid after
        being saved, regardless of what the valid field indicated before
        """
        msg = self.set_up_system_message()
        msg.valid = False

        msg.save()

        self.assertTrue(msg.valid)
        # Reload the message from the database and check again
        msg = SystemMessage.objects.all()[0]
        self.assertTrue(msg.valid)

    def test_system_message_auto_from_bot(self):
        """
        Tests that a system message is always created with the bot user.
        """
        msg = self.set_up_system_message()

        self.assertEquals(SystemMessage.get_bot_user(), msg.member)

    def test_system_message_from_bot_on_save(self):
        """
        Tests that a system message is always registered as being created
        by the system bot.
        """
        msg = self.set_up_system_message()
        msg.member = MemberFactory()

        msg.save()

        self.assertEquals(SystemMessage.get_bot_user(), msg.member)
        # Reload the message from the database and make sure it is by the bot
        msg = Message.objects.all()[0]
        self.assertEquals(SystemMessage.get_bot_user(), msg.member)
