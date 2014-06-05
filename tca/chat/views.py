from django.shortcuts import render
from django.shortcuts import get_object_or_404

from rest_framework import viewsets
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

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

    @action()
    def add_member(self, request, pk=None):
        chat_room = self.get_object()
        if 'lrz_id' not in request.DATA:
            # Invalid request
            return Response(status=status.HTTP_400_BAD_REQUEST)

        member = get_object_or_404(Member, lrz_id=request.DATA['lrz_id'])
        chat_room.members.add(member)

        return Response({
            'status': 'success',
        })
