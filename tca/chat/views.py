from django.shortcuts import render
from django.shortcuts import get_object_or_404

from rest_framework import viewsets
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from chat.models import Member
from chat.models import Message
from chat.models import ChatRoom
from chat.serializers import MemberSerializer
from chat.serializers import ChatRoomSerializer
from chat.serializers import MessageSerializer


class FilteredModelViewSetMixin(object):
    """
    A mixin providing the possibility to filter the queryset based on
    query parameters.

    The mixin overrides the ``get_queryset`` method to return the original
    queryset addiotionally filtered based on the query string parameters.

    Each additional filter is a test for direct equality.

    Classes mixing-in the Mixin should provide the ``filter_fields``
    property to provide a list of fields for which filtering should
    be supported.
    """
    filter_fields = None

    def get_queryset(self):
        qs = super(FilteredModelViewSetMixin, self).get_queryset()
        if self.filter_fields is None:
            return qs

        for filter_field in self.filter_fields:
            if filter_field in self.request.QUERY_PARAMS:
                qs = qs.filter(**{
                    filter_field: self.request.QUERY_PARAMS[filter_field]
                })

        return qs


class MemberViewSet(FilteredModelViewSetMixin, viewsets.ModelViewSet):
    model = Member
    serializer_class = MemberSerializer
    filter_fields = ('lrz_id',)


class ChatRoomViewSet(FilteredModelViewSetMixin, viewsets.ModelViewSet):
    model = ChatRoom
    serializer_class = ChatRoomSerializer
    filter_fields = ('name',)

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


class ChatMessageViewSet(viewsets.ModelViewSet):
    model = Message
    chat_room_id_field = 'chat_room'
    serializer_class = MessageSerializer

    def _chat_room_instance(self):
        """Returns the :class:`models.ChatRoom` instance that is the parent
        of the chat message(s).
        """
        return ChatRoom.objects.get(pk=self.kwargs[self.chat_room_id_field])

    def get_queryset(self):
        """
        Override the query set to get only the resources which are subordinate
        to the given ChatRoom.
        """
        return self.model.objects.filter(
            chat_room=self.kwargs[self.chat_room_id_field])

    def pre_save(self, message):
        """
        Implement the hook method to inject the corresponding parent
        ChatRoom instance to the newly created message.
        """
        message.chat_room = self._chat_room_instance()
