"""
Tests for :mod:`chat` app models.
"""

from django.test import TestCase

from chat.models import Member
from chat.models import Message
from chat.models import ChatRoom
from chat.models import PublicKey

from .factories import MemberFactory
from .factories import MessageFactory
from .factories import ChatRoomFactory
from .factories import PublicKeyFactory

import os
import json

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
            key_text=self._load_pubkey())
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
