from django.shortcuts import render

from rest_framework import viewsets

from chat.models import Member
from chat.models import ChatRoom
from chat.serializers import MemberSerializer
from chat.serializers import ChatRoomSerializer


class MemberViewSet(viewsets.ModelViewSet):
    model = Member
    serializer_class = MemberSerializer


class ChatRoomViewSet(viewsets.ModelViewSet):
    model = ChatRoom
    serializer_class = ChatRoomSerializer
