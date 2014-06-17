from __future__ import unicode_literals

from django.db import models
from django.utils.encoding import python_2_unicode_compatible

from django.core.urlresolvers import reverse


@python_2_unicode_compatible
class Member(models.Model):
    lrz_id = models.CharField(max_length=7, unique=True)
    first_name = models.CharField(max_length=30, blank=True)
    last_name = models.CharField(max_length=30, blank=True)

    def __str__(self):
        return self.lrz_id

    def get_absolute_url(self):
        return reverse('member-detail', kwargs={
            'pk': self.pk,
        })


@python_2_unicode_compatible
class PublicKey(models.Model):
    """
    A model representing a member's public key
    """
    key_text = models.TextField()
    member = models.ForeignKey(Member, related_name='public_keys')

    def __str__(self):
        return '{key} <{member}>'.format(
            key=self.key_text_encoding,
            member=self.member)

    def get_absolute_url(self):
        return reverse('publickey-detail', kwargs={
            'member': self.member.pk,
            'pk': self.pk,
        })


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
