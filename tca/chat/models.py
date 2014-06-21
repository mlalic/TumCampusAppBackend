from __future__ import unicode_literals

from django.db import models
from django.utils.encoding import python_2_unicode_compatible

from django.core.urlresolvers import reverse

from jsonfield import JSONField

from chat import crypto

import random
import string


@python_2_unicode_compatible
class Member(models.Model):
    lrz_id = models.CharField(max_length=7, unique=True)
    first_name = models.CharField(max_length=30, blank=True)
    last_name = models.CharField(max_length=30, blank=True)
    registration_ids = JSONField(default=())

    def __str__(self):
        return self.lrz_id

    def get_absolute_url(self):
        return reverse('member-detail', kwargs={
            'pk': self.pk,
        })

    @property
    def lrz_email(self):
        """
        Returns the email derived from the user's LRZ ID.
        """
        TEMPLATE = "{lrz_id}@mytum.de"

        return TEMPLATE.format(lrz_id=self.lrz_id)


@python_2_unicode_compatible
class PublicKey(models.Model):
    """
    A model representing a member's public key
    """
    key_text = models.TextField()
    member = models.ForeignKey(Member, related_name='public_keys')

    def __str__(self):
        return '{key} <{member}>'.format(
            key=self.key_text,
            member=self.member)

    def get_absolute_url(self):
        return reverse('publickey-detail', kwargs={
            'member': self.member.pk,
            'pk': self.pk,
        })


def _random_string(length=30):
    """
    Generates a random string of alphanumeric characters.
    """
    alphabet = string.ascii_letters + string.digits
    return ''.join(random.choice(alphabet) for _ in xrange(length))


@python_2_unicode_compatible
class PublicKeyConfirmation(models.Model):
    """
    Model providing a confirmation key for an uploaded public key.

    Before a public key is made active, it is necessary for the user to
    confirm it by providing the confirmation key which gets sent to his
    LRZ email address.
    """
    confirmation_key = models.CharField(
        default=_random_string,
        max_length=30,
        unique=True)
    public_key = models.ForeignKey(PublicKey)

    def __str__(self):
        return self.confirmation_key


@python_2_unicode_compatible
class ChatRoom(models.Model):
    name = models.CharField(max_length=100, unique=True)
    members = models.ManyToManyField(Member, related_name='chat_rooms')

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('chatroom-detail', kwargs={
            'pk': self.pk,
        })


@python_2_unicode_compatible
class Message(models.Model):
    text = models.TextField()
    member = models.ForeignKey(Member, related_name='messages')
    chat_room = models.ForeignKey(ChatRoom, related_name='messages')
    timestamp = models.DateTimeField(auto_now_add=True)
    signature = models.TextField(blank=True)
    valid = models.BooleanField(default=False)

    def __str__(self):
        return '{text} ({member})'.format(
            text=self.text,
            member=self.member
        )

    def get_absolute_url(self):
        return reverse('message-detail', kwargs={
            'chat_room': self.chat_room.pk,
            'pk': self.pk,
        })

    @property
    def valid_signature(self):
        """
        Return a boolean indicating whether the signature attached to the
        message matches any of the public keys associated to the user to
        which the message is related.
        """
        for pubkey in self.member.public_keys.all():
            if crypto.verify(self.text, self.signature, pubkey.key_text):
                return True

        return False

    def validate_signature(self):
        """
        Updates the validity of the message based on its signature. If the
        signature is found to match with a public key of the user with
        which it is associated, the valid ``field`` is set to ``True``.

        In case the signature is found to be invalid, the ``valid`` is
        made sure to be ``False``, but the instance is not deleted.

        The way clients handle invalid messages is left up to them.
        """
        if self.valid_signature:
            self.valid = True
            self.save()
            return True
        else:
            if self.valid:
                self.valid = False
                self.save()
            return False
