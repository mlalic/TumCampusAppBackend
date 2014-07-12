from django.shortcuts import render
from django.shortcuts import get_object_or_404
from django.utils.functional import cached_property

from django.http import Http404

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

from chat import crypto

from chat.models import Member
from chat.models import Message
from chat.models import SystemMessage
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


class SignatureValidationAPIViewMixin(object):
    """
    A mixin providing signature validation functionality.
    """
    signature_field = 'signature'
    message_field = 'message'

    def get_signature(self):
        """
        Method should return the signature which is to be validated.
        By default, returns the field of the request payload with the
        name :attr:`signature_field`.
        """
        return self.request.DATA.get(self.signature_field, None)

    def get_public_keys(self):
        """
        Returns a list of public keys which are to be matched against
        the signature. If at least one of the keys is found to match
        the signature, it will be considered valid.
        """
        return []

    def get_message_to_validate(self):
        """
        Returns the message which will be validated against the signature
        returned by :meth:`get_public_keys`.
        By default returns the field of the request payload with the
        name :attr:`message_field`.
        """
        return self.request.DATA.get(self.message_field, None)

    def validate_signature(self):
        """
        Method performs the validation of the signature based on the
        parameters of the Mixin.
        """
        message = self.get_message_to_validate()
        signature = self.get_signature()

        if not message or not signature:
            return False

        return any(
            crypto.verify(message, signature, key)
            for key in self.get_public_keys()
        )


class MemberBasedSignatureValidationMixin(SignatureValidationAPIViewMixin):
    """
    A subclass of the :class:`SignatureValidationAPIViewMixin` providing
    implementations for the methods when it is expected that the validation
    is performed based on a :class:`chat.models.Member` instance.

    The mixin assumes there is a ``member`` field on the ``self`` instance.
    """

    #: For member based validation, expect a signature field in the body
    #: of the request
    signature_field = 'signature'

    def get_message_to_validate(self):
        """
        Implement the method of the mixin to provide the message that is
        supposed to be signed for this request.

        In this case, it is simply the lrz_id of the member.
        """
        return self.member.lrz_id

    def get_public_keys(self):
        """
        Return the public keys which are to be used to try and validate
        the requests.
        """
        return [
            pubkey.key_text
            for pubkey in self.member.public_keys.filter(active=True)
        ]


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

    def post_save(self, public_key, *args, **kwargs):
        """
        Implement the hook method to initate the email confirmation of the
        new key.
        """
        hooks.confirm_new_key(public_key)


class RegistrationIdAPIView(APIView):
    """
    A base class for endpoints which will handle registration IDs.

    Registration IDs are essentially identifiers of the user's Android
    devices.
    """

    member_id_field = 'member_id'

    HTTP_422_UNPROCESSABLE_ENTITY = 422

    @cached_property
    def member(self):
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


class AddRegistrationIdView(RegistrationIdAPIView):
    def process(self):
        self.member.registration_ids.append(self.get_registration_id())

        self.member.save()


class RemoveRegistrationIdView(RegistrationIdAPIView):
    def process(self):
        try:
            self.member.registration_ids.remove(self.get_registration_id())
        except ValueError:
            # No such registration ID
            # No need to do anything special, just swallow the exception
            pass
        else:
            # If there was something removed, update the member
            self.member.save()


class ChatRoomViewSet(
        FilteredModelViewSetMixin,
        MemberBasedSignatureValidationMixin,
        viewsets.ModelViewSet):
    """
    ViewSet defining operations for the :class:`chat.models.ChatRoom`
    model.
    """

    model = ChatRoom
    serializer_class = ChatRoomSerializer
    filter_fields = ('name',)

    @action()
    def add_member(self, request, pk=None):
        chat_room = self.get_object()
        mandatory_fields = ('lrz_id', 'signature',)
        if not all(field in request.DATA for field in mandatory_fields):
            # Invalid request
            return Response(status=status.HTTP_400_BAD_REQUEST)

        self.member = get_object_or_404(
            Member, lrz_id=request.DATA['lrz_id'])

        if self.validate_signature():
            chat_room.members.add(self.member)
            # Member joined notification...
            SystemMessage.objects.create_member_joined(self.member, chat_room)
            return_status = 'success'
            status_code = status.HTTP_200_OK
        else:
            return_status = 'invalid signature'
            # Permission denied
            status_code = status.HTTP_403_FORBIDDEN

        return Response({
            'status': return_status,
        }, status=status_code)


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

        if confirmation.is_expired():
            # Expired confirmations don't count
            confirmation.delete()
            raise Http404

        public_key = confirmation.public_key
        confirmation.confirm()

        return Response({
            'public_key_text': public_key.key_text,
            'url': public_key.get_absolute_url(),
        })
