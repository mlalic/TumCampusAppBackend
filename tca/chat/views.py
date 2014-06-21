from django.shortcuts import render
from django.shortcuts import get_object_or_404

from rest_framework import viewsets
from rest_framework import status
from rest_framework import mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.renderers import (
    TemplateHTMLRenderer,
    JSONRenderer,
)

from chat.models import Member
from chat.models import Message
from chat.models import ChatRoom
from chat.models import PublicKey
from chat.models import PublicKeyConfirmation
from chat.serializers import MemberSerializer
from chat.serializers import ChatRoomSerializer
from chat.serializers import MessageSerializer
from chat.serializers import PublicKeySerializer

from chat import hooks


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


class PublicKeyViewSet(mixins.CreateModelMixin,
                       mixins.ListModelMixin,
                       mixins.RetrieveModelMixin,
                       viewsets.GenericViewSet):
    """
    A ViewSet for representing the PublicKey resource.

    It mixes in the django-rest-framework provided mixins to provide
    only the functionality of creating, listing, and retrieving public
    keys -- it disables deleting them.
    """
    model = PublicKey
    serializer_class = PublicKeySerializer
    member_id_field = 'member'

    def _member_parent_instance(self):
        """Returns the :class:`models.Member` instance that is the parent
        of the Public Keys.
        """
        return Member.objects.get(pk=self.kwargs[self.member_id_field])

    def get_queryset(self):
        """
        Override the query set to get only the resources which are subordinate
        to the given Member.
        """
        return self.model.objects.filter(
            member=self.kwargs[self.member_id_field])

    def pre_save(self, public_key):
        """
        Implement the hook method to inject the corresponding parent
        :class:`models.Member` instance to the newly created public key.
        """
        public_key.member = self._member_parent_instance()



class RegistrationIdViewMixin(object):
    """
    A mixin providing methods for views which handle registration IDs.

    Registration IDs are essentially identifiers of the user's Android
    devices.
    """

    member_id_field = 'member_id'

    HTTP_422_UNPROCESSABLE_ENTITY = 422

    def get_member(self):
        """
        Obtain a :class:`chat.models.Member` instance for the particular
        request.
        """
        return get_object_or_404(Member, pk=self.kwargs[self.member_id_field])

    def get_registration_id(self):
        """
        Returns the registration ID being referenced in the request body.
        """
        return self.request.DATA['registration_id']

    def post(self, request, member_id, format=None):
        # Validate the request
        if 'registration_id' not in self.request.DATA:
            return Response("", status=self.HTTP_422_UNPROCESSABLE_ENTITY)

        self.process()

        return Response({
            "status": "ok",
        })


class AddRegistrationIdView(RegistrationIdViewMixin, APIView):
    def process(self):
        member = self.get_member()
        member.registration_ids.append(self.get_registration_id())

        member.save()


class RemoveRegistrationIdView(RegistrationIdViewMixin, APIView):
    def process(self):
        member = self.get_member()
        try:
            member.registration_ids.remove(self.get_registration_id())
        except ValueError:
            # No such registration ID
            # No need to do anything special, just swallow the exception
            pass
        else:
            # If there was something removed, update the member
            member.save()
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

    def post_save(self, message, *args, **kwargs):
        """
        Implement the hook method to trigger the validation of the message's
        signature.
        """
        # For now the signature is validated completely synchronously to
        # the request.
        hooks.validate_message_signature(message)


class PublicKeyConfirmationView(APIView):
    """
    View providing the option for confirming a public key by knowing
    a confirmation key associated to it.

    The view is rendered to HTML unless a '.json' extension is specified
    in the URL.
    """
    renderer_classes = (
        TemplateHTMLRenderer,
        JSONRenderer,
    )

    template_name = 'confirmation-success.html'

    def get(self, request, confirmation_key, format=None):
        confirmation = get_object_or_404(
            PublicKeyConfirmation, confirmation_key=confirmation_key)
        public_key = confirmation.public_key
        confirmation.confirm()

        return Response({
            'public_key_text': public_key.key_text,
            'url': public_key.get_absolute_url(),
        })
