from rest_framework import serializers

from chat.models import Member
from chat.models import ChatRoom


class MemberSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Member


class ChatRoomSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = ChatRoom
