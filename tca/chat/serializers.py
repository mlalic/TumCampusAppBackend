from rest_framework import serializers
from rest_framework.reverse import reverse

from chat.models import Member
from chat.models import Message
from chat.models import ChatRoom


class MemberSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Member


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
