from rest_framework import serializers
from rest_framework.reverse import reverse

from chat.models import Member
from chat.models import Message
from chat.models import ChatRoom
from chat.models import PublicKey


class MemberSerializer(serializers.HyperlinkedModelSerializer):
    public_keys = serializers.SerializerMethodField('get_public_keys_url')

    class Meta:
        model = Member
        exclude = ('registration_ids',)

    def get_public_keys_url(self, member):
        return reverse(
            'publickey-list',
            kwargs={'member': member.pk},
            request=self.context.get('request', None))


class PublicKeySerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.SerializerMethodField('get_url')

    read_only_fields = ('active',)

    class Meta:
        model = PublicKey
        exclude = (
            'member',
        )

    def __init__(self, *args, **kwargs):
        """
        Override the init method to set some fields as read only.
        """
        super(PublicKeySerializer, self).__init__(*args, **kwargs)
        for field_name in self.read_only_fields:
            self.fields[field_name].read_only = True

    def get_url(self, public_key):
        """Customized version of obtaining the object's URL.
        Necessary because the resource is a subordinate of a chatroom
        resource, so it is necessary to include the parent's ID in the
        URL.
        """
        return reverse(
            'publickey-detail', kwargs={
                'member': public_key.member.pk,
                'pk': public_key.pk,
            },
            request=self.context.get('request', None)
        )


class ChatRoomSerializer(serializers.HyperlinkedModelSerializer):
    messages = serializers.SerializerMethodField('get_messages_url')

    def get_messages_url(self, chat_room):
        return reverse(
            'message-list',
            kwargs={'chat_room': chat_room.pk},
            request=self.context.get('request', None)
        )

    class Meta:
        model = ChatRoom


class MessageSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.SerializerMethodField('get_url')

    def get_url(self, message):
        """Customized version of obtaining the object's URL.
        Necessary because the resource is a subordinate of a chatroom
        resource, so it is necessary to include the parent's ID in the
        URL.
        """
        return reverse(
            'message-detail', kwargs={
                'chat_room': message.chat_room.pk,
                'pk': message.pk,
            },
            request=self.context.get('request', None)
        )

    class Meta:
        model = Message
        exclude = ('chat_room',)
        read_only_fields = ('valid',)
