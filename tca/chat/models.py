from __future__ import unicode_literals

from django.db import models
from django.utils.encoding import python_2_unicode_compatible


@python_2_unicode_compatible
class Member(models.Model):
    lrz_id = models.CharField(max_length=7, unique=True)
    first_name = models.CharField(max_length=30, blank=True)
    last_name = models.CharField(max_length=30, blank=True)

    def __str__(self):
        return self.lrz_id


@python_2_unicode_compatible
class ChatRoom(models.Model):
    name = models.CharField(max_length=100)
    members = models.ManyToManyField(Member, related_name='chat_rooms')

    def __str__(self):
        return self.name


@python_2_unicode_compatible
class Message(models.Model):
    text = models.TextField()
    member = models.ForeignKey(Member, related_name='messages')
    chat_room = models.ForeignKey(ChatRoom, related_name='messages')

    def __str__(self):
        return '{text} ({member})'.format(
            text=self.text,
            member=self.member
        )
