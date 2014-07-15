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


class PartialChatRoomSerializer(serializers.ModelSerializer):
    """
    A serializer for the :class:`chat.models.ChatRoom` model which
    includes only a partial representation of the resource.

    Useful when we want to reduce the amount of data transferred over
    the network and only most important information about the resource
    is required.
    """
    class Meta:
        model = ChatRoom
        # Include only the ID of the chat room
        fields = ('id',)


class MessageSerializerMixin(object):
    """
    A mixin for serializers wishing to serialize the
    :class:`chat.models.Message` models.

    It provides the default ``Meta`` settings for the objects, as well
    as a convenience method for obtaining the URL of a message.

    Classes mixing it in need to override any field they want to
    deviate from their base serializer's implementation.
    """
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
        read_only_fields = (
            'valid',
        )

    def __init__(self, *args, **kwargs):
        super(MessageSerializerMixin, self).__init__(*args, **kwargs)
        self.fields['chat_room'].read_only = True


class MessageSerializer(MessageSerializerMixin, serializers.HyperlinkedModelSerializer):
    """
    A serializer for the :class:`chat.models.Message` model.

    Treats the :class:`chat.models.Member` instance associated to the
    message as a hyperlink.  It is suitable for creating new messages.
    """
    url = serializers.SerializerMethodField('get_url')


class ListMessageSerializer(MessageSerializerMixin, serializers.ModelSerializer):
    """
    A serializer for the :class:`chat.models.Message` model.

    Treats the :class:`chat.models.Member` instance associated to the
    message as a nested resource.  It is suitable for listing messages.
    """
    url = serializers.SerializerMethodField('get_url')
    member = MemberSerializer()
    chat_room = PartialChatRoomSerializer()
