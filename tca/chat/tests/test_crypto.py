"""
Tests for the :mod:`chat.crypto` module which implements basic crypto
functionality which is needed across different views.
"""

from django.test import TestCase

from chat import crypto

import json
import os


class VerifySignatureTestCase(TestCase):
    """
    Tests for the :func:`chat.crypto.verify` function of the
    :mod:`chat.crypto` module.
    """
    @classmethod
    def get_fixture_path(cls, fixture_file_name):
        """Returns the path to a fixture files for this TestCase."""
        base_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(
            base_dir,
            'fixtures',
            fixture_file_name)

    def setUp(self):
        # Load message/signature fixtures
        with open(self.get_fixture_path('message_fixtures.json')) as f:
            self.message_fixtures = json.load(f)
        # Set up a fixture public key
        with open(self.get_fixture_path('pubkey.pub'), 'rb') as pubkey_file:
            data = pubkey_file.read()
        # Make sure the public key is unicode too
        self.public_key = data.decode('utf-8')

    def test_simple_message(self):
        """
        Tests that a simple (ASCII) message's signature is correctly
        verified.
        """
        message = self.message_fixtures['simple-message']

        result = crypto.verify(
                message['text'],
                message['signature'],
                self.public_key)

        self.assertTrue(result)

    def test_message_unicode_easy(self):
        """
        Tests that a message containing non-ASCII German characters
        is correctly verified.
        """
        message = self.message_fixtures['unicode-1']

        result = crypto.verify(
                message['text'],
                message['signature'],
                self.public_key)

        self.assertTrue(result)

    def test_message_unicode_korean(self):
        """
        Tests that a message containing non-ASCII Korean characters is
        correctly verified.
        """
        message = self.message_fixtures['unicode-korean']

        result = crypto.verify(
                message['text'],
                message['signature'],
                self.public_key)

        self.assertTrue(result)

    def test_invalid_signature(self):
        """
        Tests that a message with an invalid signature is correctly
        recognized.
        """
        message = self.message_fixtures['simple-message']
        # Replace the first character with a different one making the
        # signature invalid
        message['signature'] = '*' + message['signature'][1:]

        result = crypto.verify(
            message['text'],
            message['signature'],
            self.public_key)

        self.assertFalse(result)

    def test_invalid_base64(self):
        """
        Tests that the message is not marked valid when the signature
        is represented by an invalid base64 string.
        """
        message = self.message_fixtures['simple-message']
        message['signature'] = 'asd'

        result = crypto.verify(
            message['text'],
            message['signature'],
            self.public_key)

        self.assertFalse(result)

    def test_invalid_public_key(self):
        """
        Tests that a message is not marked valid when the provided
        public key is not valid.
        """
        message = self.message_fixtures['simple-message']

        result = crypto.verify(
            message['text'],
            message['signature'],
            'asd')

        self.assertFalse(result)

    def test_message_is_none(self):
        """
        Tests that when the message parameter is ``None``, the message
        is not considered valid.
        """
        message = self.message_fixtures['unicode-korean']

        result = crypto.verify(
                None,
                message['signature'],
                self.public_key)

        self.assertFalse(result)

    def test_signature_is_none(self):
        """
        Tests that when the signature parameter is ``None``, the message
        is not considered valid.
        """
        message = self.message_fixtures['unicode-korean']

        result = crypto.verify(
                message['text'],
                None,
                self.public_key)

        self.assertFalse(result)

    def test_public_key_is_none(self):
        """
        Tests that when the public_key parameter is ``None``, the message
        is not considered valid.
        """
        message = self.message_fixtures['unicode-korean']

        result = crypto.verify(
                message['text'],
                message['signature'],
                None)

        self.assertFalse(result)
