from django.shortcuts import render
from django.shortcuts import get_object_or_404
from django.utils.functional import cached_property
from django.db.models import fields as django_fields
from django.core.paginator import (
    Paginator,
    EmptyPage,
)

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
from rest_framework.templatetags.rest_framework import replace_query_param

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
from chat.serializers import ListMessageSerializer
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

        for filter_field_name in self.filter_fields:
            if filter_field_name in self.request.QUERY_PARAMS:
                filter_value = self.request.QUERY_PARAMS[filter_field_name]

                # Special casing the value which is passed to the QS
                # filter method for certain types of fields
                field = self.model._meta.get_field(filter_field_name)
                if isinstance(field, django_fields.BooleanField):
                    filter_value = filter_value.lower()
                    if filter_value not in ('true', 'false'):
                        # Ignore the filter if the value is invalid
                        continue

                    filter_value = filter_value.lower() == 'true'

                qs = qs.filter(**{
                    filter_field_name: filter_value,
                })

        return qs


class PaginatedListModelMixin(object):
    """
    A mixin providing seamless pagination of list responses.

    The difference to the behavior of the
    :class:`rest_framework.mixins.ListModelMixin` is that the pagination
    links are included in the HTTP ``Link`` header instead of enveloping
    the results of the endpoint in a JSON object with a "results" field.
    """
    default_page_size = 5
    page_size_parameter = 'page_size'
    paging_parameter = 'page'
    paginator_class = Paginator

    def get_page_size(self):
        """
        Method returns the size of the page which should be returned.

        The default implementation returns either the size given in the
        query string parameter named :attr:`page_size_parameter` (if
        given and a valid integer) or the default size given by the
        :attr:`default_page_size` property.
        """
        page_size = self.default_page_size

        if self.page_size_parameter in self.request.QUERY_PARAMS:
            try:
                page_size = int(
                    self.request.QUERY_PARAMS[self.page_size_parameter])
            except ValueError:
                pass

        return page_size

    def get_paginator_instance(self, object_list):
        """
        Get a paginator instance which can be used to retrieve pages of
        objects.

        The paginator instance should be able to provide pages identified
        by the identifiers being returned by the :meth:`get_page_identifier`
        method.

        By default, the method constructs a paginator based on the
        :attr:`paginator_class` property by passing it the given object list
        and the page size.
        """
        return self.paginator_class(object_list, self.get_page_size())

    def get_page_identifier(self):
        """
        Return the identifier of the page which should be returned for
        this request.

        In the default implementation the identifiers are integers
        representing the page numbers.

        The default implementation returns the value of the query string
        parameter named ``paging_parameter``.

        If there is no such parameter or it does not have a valid integer
        value, returns the first page.
        """
        page = 1

        if self.paging_parameter in self.request.QUERY_PARAMS:
            page = self.request.QUERY_PARAMS[self.paging_parameter]
            try:
                page = int(page)
            except ValueError:
                page = 1

        return page

    def build_page_url(self, page_identifier):
        """
        Builds a URL which can be used to access the given page identifer.

        In the general case, the page identifiers do not have to be numbers.
        """
        url = self.request.build_absolute_uri()
        return replace_query_param(url, self.paging_parameter, page_identifier)

    def generate_link(self, rel, page_identifier):
        """
        Generates a link for the given page with the given ``rel`` name.
        """
        LINK_TEMPLATE = '<{url}>; rel="{rel}"'

        url = self.build_page_url(page_identifier)
        return LINK_TEMPLATE.format(url=url, rel=rel)

    def add_pagination_links(self, response):
        """
        Adds the pagination links already prepared and found in the
        :attr:`pagination_links` property to the given HttpResponse instance.

        The links are to be found in the ``Link`` HTTP header.
        """
        links = ', '.join((
            self.generate_link(rel, page_number)
            for rel, page_number in self.pagination_links.items()
        ))

        if links:
            # Add the header only if there were some links generated
            response['Link'] = links

    def set_up_pagination_links(self, page):
        """
        Sets up the pagination links which are to be included in the
        HTTP ``Link`` header.

        The links are based on the given page parameter.
        """
        self.pagination_links = {}
        if page is None:
            return

        if page.has_next():
            self.pagination_links['next'] = page.next_page_number()
        if page.has_previous():
            self.pagination_links['prev'] = page.previous_page_number()

    def paginate(self, object_list):
        """
        Performs the pagination step.

        :param object_list: The list of objects which should be paginated

        :returns: A list of objects which should be returned as a result
            of the current request.
        """
        paginator = self.get_paginator_instance(object_list)
        pagination_links = {}
        try:
            page = paginator.page(self.get_page_identifier())
        except EmptyPage:
            results = []
            page = None
        else:
            results = page.object_list

        # After the results for the current request have been found,
        # prepare the pagination links which will later be added to the
        # ``Link`` header of the HTTP response
        self.set_up_pagination_links(page)

        return results

    def list(self, request, *args, **kwargs):
        """
        An implementation of the list method which obtains the same
        object list as the :class:`rest_framework.mixins.ListModelMixin`
        would, but returns the results paginated in a different manner.
        """
        # Keep the same expected behavior as the DRF list mixin would have
        self.object_list = self.filter_queryset(self.get_queryset())
        # Get a list of objects to return
        self.object_list = self.paginate(self.object_list)

        # Now prepare the response content
        serializer = self.get_serializer(self.object_list, many=True)
        response = Response(serializer.data)
        # Add the appropriate links
        self.add_pagination_links(response)

        return response


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


class MultiSerializerViewSetMixin(object):
    """
    Mixin for the DRF ViewSet providing the ability to choose a different
    serializer based on the view action.

    Classes mixing it in need to provide the ``serializer_classes``
    dictionary mapping an action to a serializer class.

    If a particular action does not have a custom serializer attached to it,
    the mixin delegates the call up the MRO (Method Resolution Order).

    Example usage::

        from rest_framework import viewsets


        class ModelViewSet(MultiSerializerViewSetMixin, viewsets.ModelViewSet):
            model = SomeModel
            #: Provide a default model serializer like usual
            serializer_class = DefaultModelSerializer
            #: Provide an overide for the serializer for two actions
            serializer_classes = {
                'list': ListModelSerializer,
                'create': CreateModelSerializer,
            }
    """
    def get_serializer_class(self):
        if self.action in self.serializer_classes:
            return self.serializer_classes[self.action]

        return super(MultiSerializerViewSetMixin, self).get_serializer_class()


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


class RegistrationIdAPIView(MemberBasedSignatureValidationMixin, APIView):
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

        if not self.validate_signature():
            return Response({
                'status': 'invalid signature',
            }, status=status.HTTP_403_FORBIDDEN)

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

    @action()
    def remove_member(self, request, pk=None):
        chat_room = self.get_object()
        mandatory_fields = ('lrz_id', 'signature',)
        if not all(field in request.DATA for field in mandatory_fields):
            # Invalid request
            return Response(status=status.HTTP_400_BAD_REQUEST)

        self.member = get_object_or_404(
            Member, lrz_id=request.DATA['lrz_id'])

        if self.validate_signature():
            chat_room.members.remove(self.member)
            # Member left notification...
            SystemMessage.objects.create_member_left(self.member, chat_room)
            return_status = 'success'
            status_code = status.HTTP_200_OK
        else:
            return_status = 'invalid signature'
            # Permission denied
            status_code = status.HTTP_403_FORBIDDEN

        return Response({
            'status': return_status,
        }, status=status_code)


class ChatMessageViewSet(
        MultiSerializerViewSetMixin,
        FilteredModelViewSetMixin,
        viewsets.ModelViewSet):

    model = Message
    chat_room_id_field = 'chat_room'

    filter_fields = ('valid',)

    #: The default serializer to be used for the ViewSet
    serializer_class = MessageSerializer
    #: A dictionary of serializers to override the default one depending
    #: on the action being taken.
    serializer_classes = {
        'list': ListMessageSerializer,
    }

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
        qs = super(ChatMessageViewSet, self).get_queryset()
        return qs.filter(chat_room=self.kwargs[self.chat_room_id_field])

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
