from django.test import TestCase
from django.test.utils import override_settings

from django.core.urlresolvers import reverse

from django.utils import timezone

from urllib import urlencode

import json
import mock
import datetime

from chat.views import MemberBasedSignatureValidationMixin

from chat.models import Member
from chat.models import Message
from chat.models import ChatRoom
from chat.models import PublicKey
from chat.models import PublicKeyConfirmation

from .factories import MemberFactory
from .factories import MessageFactory
from .factories import ChatRoomFactory
from .factories import PublicKeyFactory


class ViewTestCaseMixin(object):
    """A mixin providing some convenience methods for testing views.

    Expects that a ``view_name`` property exists on the class which
    mixes it in.
    """

    def get_view_url(self, *args, **kwargs):
        return reverse(self.view_name, args=args, kwargs=kwargs)

    def build_url(self, base_url, query_dict=None):
        url_template = "{base_url}?{query_string}"

        if query_dict is None:
            return base_url

        return url_template.format(
            base_url=base_url,
            query_string=urlencode(query_dict)
        )

    def get(self, parameters=None, *args, **kwargs):
        """
        Sends a GET request to the view-under-test and returns the response

        :param parameters: The query string parameters of the GET request
        """
        base_url = self.get_view_url(*args, **kwargs)

        return self.client.get(self.build_url(base_url, parameters))

    def post(self, body=None, content_type='application/json', *args, **kwargs):
        """
        Sends a POST request to the view-under-test and returns the response

        :param body: The content to be included in the body of the request
        """
        base_url = self.get_view_url(*args, **kwargs)

        if body is None:
            body = ''

        return self.client.post(
            self.build_url(base_url),
            body,
            content_type=content_type)

    def post_json(self, json_payload, *args, **kwargs):
        """
        Sends a POST request to the view-under-test and returns the response.
        The body of the POST request is formed by serializing the
        ``json_payload`` object to JSON.
        """
        payload = json.dumps(json_payload)

        return self.post(
            body=payload,
            content_type='application/json',
            *args, **kwargs)


class MemberListViewTestCase(ViewTestCaseMixin, TestCase):
    """
    Tests for the REST endpoint which deals with a list of members. This
    endpoint should provide POST and GET methods which allow the creation of
    new members and listing exsting ones, respectivelly.
    """

    view_name = 'member-list'

    # Relevant fields of the Member model
    FIELDS = (
        'lrz_id',
        'display_name',
    )

    def extract_member_fields(self, member, exclude=None):
        """
        Helper method to extract fields of a member into a dict
        """
        if exclude is None:
            exclude = ()

        return {
            field_name: getattr(member, field_name)
            for field_name in self.FIELDS
            if not field_name in exclude
        }

    def test_create_member(self):
        """
        Tests if a new member is successfully created when POSTing to this
        view.
        """
        new_member = MemberFactory.attributes()

        response = self.post_json(new_member)

        # -- Assert correct actions taken
        # Member created
        self.assertEqual(Member.objects.count(), 1)
        # Member has correct attributes
        member = Member.objects.all()[0]
        self.assertDictEqual(
            new_member,
            self.extract_member_fields(member))

        # -- Assert correct response
        # Correct status code
        self.assertEqual(201, response.status_code)
        # Content correctly represents the created resource
        response_object = json.loads(response.content)
        # All values are correctly found
        for key, value in new_member.items():
            self.assertEquals(
                value,
                response_object[key])
        # ...additionally a URL is created and assigned to the resource
        self.assertIn('url', response_object)
        # The URL is the member detail representation
        self.assertTrue(response_object['url'].endswith(
            reverse('member-detail', kwargs={'pk': member.pk})))

    def test_create_duplicate_member(self):
        """
        Test that it is not possible to create a member with the same lrz_id
        """
        # Set up a member
        existing_member = MemberFactory.create()
        # Create a payload which would duplicate the member
        new_member = MemberFactory.attributes()
        new_member['lrz_id'] = existing_member.lrz_id

        response = self.post_json(new_member)

        # The response indicates that it was not possible to create a new member
        self.assertEquals(400, response.status_code)
        # Still only one member
        self.assertEquals(Member.objects.count(), 1)

    def test_partial_create(self):
        """
        Tests that it is possible to create a member with only an lrz_id.
        """
        new_member = {
            'lrz_id': 'asdfg',
        }

        response = self.post_json(new_member)

        self.assertEquals(201, response.status_code)
        self.assertEquals(1, Member.objects.count())

    def test_no_lrz_id_provided(self):
        """
        Tests that it is not possible to create a member with no LRZ ID.
        """
        new_member = MemberFactory.attributes()
        del new_member['lrz_id']

        response = self.post_json(new_member)

        self.assertEquals(400, response.status_code)
        self.assertEquals(0, Member.objects.count())

    def test_list_members(self):
        """
        Tests that issuing a GET request to the view correctly returns a list
        of all existing members.
        """
        # Create some members
        member_count = 10
        members = MemberFactory.create_batch(member_count)

        response = self.get()

        # The response status code is correct
        self.assertEquals(200, response.status_code)
        response_content = json.loads(response.content)
        # All members are found in the response
        self.assertEqual(member_count, len(response_content))
        # Each of them is correct?
        for member_dict, member in zip(response_content, members):
            expected_dict = self.extract_member_fields(member)
            for key, value in expected_dict.items():
                self.assertEquals(value, member_dict[key])
            # URL included too?
            self.assertTrue(member_dict['url'].endswith(
                reverse('member-detail', kwargs={'pk': member.pk})))


    def test_filter_list_by_lrz_id(self):
        """
        Test that it is possible to filter the list of members by providing
        an LRZ ID in the query string.
        """
        member_count = 10
        members = MemberFactory.create_batch(member_count)
        member_to_get = members[5]

        response = self.get({
            'lrz_id': member_to_get.lrz_id,
        })

        # Status code indicates success
        self.assertEquals(200, response.status_code)
        # The response contains the correct member?
        response_content = json.loads(response.content)
        # Only one instance is found in the response (necessarily only one
        # since the lrz_id is unique)
        self.assertEquals(1, len(response_content))
        # Correct object returned
        expected_dict = self.extract_member_fields(member_to_get)
        member_dict = response_content[0]
        for key, value in expected_dict.items():
            self.assertEquals(value, member_dict[key])
        # URL included too?
        self.assertTrue(member_dict['url'].endswith(
            reverse('member-detail', kwargs={'pk': member_to_get.pk})))

    def test_filter_list_by_lrz_id_no_match(self):
        """
        Tests that when filtering the list of members and there is no matching
        member found, an empty list is returned.
        """
        member = MemberFactory.create()
        # Just build a string which is necessarily different than the existing
        # member's id
        query_id = member.lrz_id + 'a'

        response = self.get({
            'lrz_id': query_id,
        })

        # Status code indicates success
        self.assertEquals(200, response.status_code)
        # There are no objects in the list
        response_content = json.loads(response.content)
        self.assertEquals(0, len(response_content))


class MessageListTestCase(ViewTestCaseMixin, TestCase):
    """
    Tests for the REST endpoint for a list of messages: the endpoint needs
    to be able to create a new message and list all existing messages.
    """
    view_name = 'message-list'

    def setUp(self):
        # Random members to fill up the database
        MemberFactory.create_batch(2)
        # Member that will be posting messages
        self.member = MemberFactory.create()
        # Random chat rooms to fill up the database
        ChatRoomFactory.create_batch(5)
        # Chat room to which the test messages will be posted
        self.chat_room = ChatRoomFactory.create()

    def _build_message_json(self, text, member):
        """
        Helper method which creates a Python dict representing the Message.
        This dict is one suitable to be sent as a payload to the chat message
        REST endpoint for creating a new chat message.
        """
        return {
            'text': text,
            'member': member.get_absolute_url(),
        }

    @mock.patch('chat.views.hooks.validate_message_signature')
    def test_create_message(self, mock_validate_signature):
        """
        Tests that it creating a message (as a subordinate resource to an
        existing chat room) is possible.
        """
        new_message_dict = self._build_message_json(
            text='message text...',
            member=self.member)

        response = self.post_json(new_message_dict, chat_room=self.chat_room.pk)

        # -- Actions are correct?
        # Message created?
        self.assertEquals(1, Message.objects.count())
        message = Message.objects.all()[0]
        # Message in the correct chat room?
        self.assertEquals(message.chat_room.pk, self.chat_room.pk)
        # Associated to the correct member?
        self.assertEquals(message.member.pk, self.member.pk)
        # Is not marked as valid yet?
        self.assertFalse(message.valid)
        # Validation was triggered, though?
        mock_validate_signature.assert_called_once_with(message)
        # -- Correct response
        # The response indicates a successfully created message
        self.assertEquals(201, response.status_code)
        # The response contains a representation of the created message
        response_content = json.loads(response.content)
        self.assertEquals(
                response_content['text'],
                new_message_dict['text'])
        # Has an automatic time stamp?
        self.assertIn('timestamp', response_content)
        # Links to the member who posted it?
        self.assertTrue(response_content['member'].endswith(
            self.member.get_absolute_url()))
        # Has a link for message details?
        self.assertTrue(response_content['url'].endswith(
            message.get_absolute_url()))

    @mock.patch('chat.views.hooks.validate_message_signature')
    def test_create_message_valid_field_override(
            self, mock_validate_signature):
        """
        Test that when a new message is created through the REST endpoint,
        the valid field cannot be overridden.
        """
        new_message_dict = self._build_message_json(
            text='message text...',
            member=self.member)
        new_message_dict['valid'] = True

        response = self.post_json(
                new_message_dict,
                chat_room=self.chat_room.pk)

        self.assertEquals(1, Message.objects.count())
        message = Message.objects.all()[0]
        self.assertFalse(message.valid)

    def test_list_messages(self):
        """
        Tests that it is possible to list all existing messages of a chat
        room.
        """
        # Set up some messages to the chat room
        message_count = 5
        messages = MessageFactory.create_batch(
            message_count, chat_room=self.chat_room)
        # Create some chat messages to a different chat room
        MessageFactory.create_batch(5,
                chat_room=ChatRoom.objects.exclude(pk=self.chat_room.pk)[0])

        response = self.get(chat_room=self.chat_room.pk)

        # Correct response status code
        self.assertEquals(200, response.status_code)
        # All the messages are returned?
        response_content = json.loads(response.content)
        self.assertEquals(message_count, len(response_content))
        for message, response_message in zip(messages, response_content):
            self.assertEquals(message.text, response_message['text'])


class PublicKeyListTestCase(ViewTestCaseMixin, TestCase):
    """
    Tests for the REST endpoint for a list of public keys: the endpoint
    needs to be able to create a new public key and list all existing
    public keys.
    """

    view_name = 'publickey-list'

    def setUp(self):
        MemberFactory.create_batch(5)
        self.member = MemberFactory.create()

    @mock.patch('chat.views.hooks.confirm_new_key')
    def test_create_public_key(self, mock_confirm):
        # Even though the text doesn't really represent a valid RSA key
        # it is enough to test the service endpoint's correctness
        key_text = 'asdf'
        request_object = {
            'key_text': key_text,
        }

        response = self.post_json(request_object, member=self.member.pk)

        # -- Correct actions?
        self.assertEquals(1, PublicKey.objects.count())
        pubkey = PublicKey.objects.all()[0]
        self.assertEquals(pubkey.key_text, key_text)
        # Associated to the correct member?
        self.assertEquals(pubkey.member.pk, self.member.pk)
        # Ran the hook to confirm the key
        mock_confirm.assert_called_once_with(pubkey)
        # -- Correct response?
        # The status code indicates a created resource
        self.assertEquals(201, response.status_code)
        # Contains the resource representation
        response_content = json.loads(response.content)
        self.assertEquals(response_content['key_text'], key_text)

    def test_list_public_keys(self):
        """
        Tests that the endpoint lists all public keys associated with
        a single member.
        """
        key_count = 2
        pubkeys = PublicKeyFactory.create_batch(
                key_count, member=self.member)
        # Create some other keys associated to different members
        PublicKeyFactory.create_batch(
                5,
                member=Member.objects.exclude(pk=self.member.pk)[0])
        PublicKeyFactory.create_batch(
                5,
                member=Member.objects.exclude(pk=self.member.pk)[1])

        response = self.get(member=self.member.pk)

        # Success
        self.assertEquals(200, response.status_code)
        # All the correct keys are returned
        response_content = json.loads(response.content)
        self.assertEquals(2, len(response_content))


class AddRegistrationIdTestCase(ViewTestCaseMixin, TestCase):
    """
    Tests for adding a new registration ID to a :class:`chat.models.Member`
    """

    view_name = 'add-registration-id'

    def setUp(self):
        self.member = MemberFactory.create()

    def reload_member(self):
        """
        Helper method which reloads the ``member`` instance from
        the database.
        """
        self.member = Member.objects.get(pk=self.member.pk)

    @mock.patch('chat.views.RegistrationIdAPIView.validate_signature')
    def test_add_registration_id(self, mock_validate):
        """
        Tests that adding a registration ID works correctly when the
        existing member has no registration IDs associated.
        """
        registration_id = 'kfds43vb'
        mock_validate.return_value = True

        response = self.post_json({
            'registration_id': registration_id,
            'signature': 'asdf',
        }, member_id=self.member.pk)

        self.assertEquals(200, response.status_code)
        self.reload_member()
        # Registration ID in the list?
        self.assertEquals(1, len(self.member.registration_ids))
        # Correct value?
        self.assertEquals(
            registration_id,
            self.member.registration_ids[0])
    
    @mock.patch('chat.views.RegistrationIdAPIView.validate_signature')
    def test_add_registration_id_existing(self, mock_validate):
        """
        Tests that adding a registration ID to a Member with some IDs
        already associated to it works correctly
        """
        mock_validate.return_value = True
        initial_ids = ["asdf", "bdsa"]
        self.member.registration_ids = initial_ids
        self.member.save()
        self.reload_member()
        # Sanity check
        self.assertListEqual(initial_ids, self.member.registration_ids)

        new_id = "thisisanewid"
        response = self.post_json({
            'registration_id': new_id,
            'signature': 'asdf',
        }, member_id=self.member.pk)

        self.assertEquals(200, response.status_code)
        self.reload_member()
        self.assertListEqual(
            initial_ids + [new_id],
            self.member.registration_ids)

    def test_add_registration_id_invalid_json(self):
        """
        Tests the response to an invalid JSON payload.
        """
        response = self.post(
            "this is not valid JSON",
            member_id=self.member.pk)

        self.assertEquals(400, response.status_code)

    def test_no_registration_id_in_request(self):
        """
        Tests the response to a request containing a valid JSON payload,
        but which does not contain a ``registration_id`` field.
        """
        response = self.post_json({
            'key': 'value',
        }, member_id=self.member.pk)

        self.assertEquals(422, response.status_code)

    def test_non_existent_member(self):
        """
        Tests the response to a request issued to a non-existent member
        resource.
        """
        response = self.post_json({
            'registration_id': 'asdf',
        }, member_id=self.member.pk + 5)

        self.assertEquals(404, response.status_code)

    @mock.patch('chat.views.RegistrationIdAPIView.validate_signature')
    def test_invalid_signature(self, mock_validate):
        """
        Test that a registration id is added if the signature is found to
        be invalid.
        """
        mock_validate.return_value = False
        registration_id = 'kfds43vb'

        response = self.post_json({
            'registration_id': registration_id,
            'signature': 'asdf',
        }, member_id=self.member.pk)

        # Forbidden
        self.assertEquals(403, response.status_code)
        self.reload_member()
        # Registration ID not in the list?
        self.assertEquals(0, len(self.member.registration_ids))


class RemoveRegistrationIdTestCase(ViewTestCaseMixin, TestCase):
    """
    Tests for removing a registration ID from a :class:`chat.models.Member`
    """

    view_name = 'remove-registration-id'

    def setUp(self):
        self.member = MemberFactory.create()

        self.initial_ids = ["asdf", "fdsa"]
        self.member.registration_ids = self.initial_ids
        self.member.save()
        self.reload_member()

    def reload_member(self):
        """
        Helper method which reloads the ``member`` instance from
        the database.
        """
        self.member = Member.objects.get(pk=self.member.pk)

    @mock.patch('chat.views.RegistrationIdAPIView.validate_signature')
    def test_remove_registration_id(self, mock_validate):
        """
        Tests that removing a registration ID works correctly.
        """
        mock_validate.return_value = True
        registration_id = self.initial_ids[0]

        response = self.post_json({
            'registration_id': registration_id,
            'signature': 'asdf',
        }, member_id=self.member.pk)

        self.assertEquals(200, response.status_code)
        self.reload_member()
        # Registration ID not in the list?
        self.assertNotIn(registration_id, self.member.registration_ids)
        expected_list = self.initial_ids[:]
        expected_list.remove(registration_id)
        self.assertListEqual(expected_list, self.member.registration_ids)
    
    @mock.patch('chat.views.RegistrationIdAPIView.validate_signature')
    def test_registration_id_non_existent(self, mock_validate):
        """
        Tests that trying to remove a registration ID which is not
        associated to a particular member does not cause any errors.
        """
        mock_validate.return_value = True
        registration_id = 'id-not-in-initial-list'
        # Sanity check
        self.assertNotIn(registration_id, self.initial_ids,
                         "Sanity check failure -- invalid test fixture.")

        response = self.post_json({
            'registration_id': registration_id,
            'signature': 'asdf',
        }, member_id=self.member.pk)

        self.assertEquals(200, response.status_code)
        self.reload_member()
        # Registration ID not in the list?
        self.assertNotIn(registration_id, self.member.registration_ids)
        # List not modified?
        self.assertListEqual(self.initial_ids, self.member.registration_ids)

    def test_invalid_json(self):
        """
        Tests the response to an invalid JSON payload.
        """
        response = self.post(
            "this is not valid JSON",
            member_id=self.member.pk)

        self.assertEquals(400, response.status_code)

    def test_no_registration_id_in_request(self):
        """
        Tests the response to a request containing a valid JSON payload,
        but which does not contain a ``registration_id`` field.
        """
        response = self.post_json({
            'key': 'value',
        }, member_id=self.member.pk)

        self.assertEquals(422, response.status_code)

    def test_non_existent_member(self):
        """
        Tests the response to a request issued to a non-existent member
        resource.
        """
        response = self.post_json({
            'registration_id': 'asdf',
        }, member_id=self.member.pk + 5)

        self.assertEquals(404, response.status_code)

    @mock.patch('chat.views.RegistrationIdAPIView.validate_signature')
    def test_invalid_signature(self, mock_validate):
        """
        Tests that the registration id is not removed if
        the signature is found to be invalid.
        """
        mock_validate.return_value = False
        registration_id = self.initial_ids[0]

        response = self.post_json({
            'registration_id': registration_id,
            'signature': 'asdf',
        }, member_id=self.member.pk)

        # Forbidden status code
        self.assertEquals(403, response.status_code)
        self.reload_member()
        # Registration ID still in the list?
        self.assertIn(registration_id, self.member.registration_ids)
        # No changes from the initial list?
        expected_list = self.initial_ids[:]
        self.assertListEqual(expected_list, self.member.registration_ids)


class PublicKeyConfirmationViewTestCase(ViewTestCaseMixin, TestCase):
    """
    Tests for the view which is used to confirm the validity of a
    public key.
    """
    view_name = 'confirmation-view'

    def setUp(self):
        self.members = MemberFactory.create_batch(5)
        self.member = self.members[1]

        self.dummy_key_text = 'dummy-key-text'
        self.public_key = self.member.public_keys.create(
            key_text=self.dummy_key_text)
        # Get a canonical now-time for public key confirmations
        self.now = timezone.now()

    def set_up_confirmation(self, public_key):
        """
        Helper method which sets up a PublicKeyConfirmation instance for
        the given public key.
        """
        return PublicKeyConfirmation.objects.create(public_key=public_key)

    @override_settings(TCA_CONFIRMATION_EXPIRATION_HOURS=2)
    def test_confirm_key(self):
        """
        Tests that confirming an existing key works as expected.
        """
        confirmation = self.set_up_confirmation(self.public_key)
        # Sanity check: a confirmation exists
        self.assertEquals(1, PublicKeyConfirmation.objects.count())
        # Sanity check: the public key is not active
        self.assertFalse(self.public_key.active)

        response = self.get(confirmation_key=confirmation.confirmation_key)

        # Correct response?
        self.assertEquals(200, response.status_code)
        self.assertIn('text/html', response['Content-Type'])
        # Rendered the correct template?
        self.assertTemplateUsed(response, 'confirmation-success.html')
        self.assertEquals(
            self.public_key.key_text,
            response.context['public_key_text'])
        self.assertTrue(response.context['url'].endswith(
            self.public_key.get_absolute_url()))
        self.assertContains(response, self.public_key.key_text)
        # Correct actions?
        # The confirmation is removed
        self.assertEquals(0, PublicKeyConfirmation.objects.count())
        # The public key is enabled
        # (reload the PK from the database first)
        self.public_key = PublicKey.objects.get(pk=self.public_key.pk)
        self.assertTrue(self.public_key.active)

    @override_settings(TCA_CONFIRMATION_EXPIRATION_HOURS=2)
    def test_non_existent_confirmation_key(self):
        """
        Tests the view when a non-exitent confirmation key is passed to it
        """
        confirmation = self.set_up_confirmation(self.public_key)

        response = self.get(confirmation_key='this-key-does-not-exist')

        self.assertEquals(404, response.status_code)
        self.assertEquals(1, PublicKeyConfirmation.objects.count())

    @override_settings(TCA_CONFIRMATION_EXPIRATION_HOURS=2)
    def test_public_key_removed(self):
        """
        Tests the view when the public key associated to the confirmation
        was removed in the mean time.
        """
        # Set up a confirmation
        confirmation = self.set_up_confirmation(self.public_key)
        # But now delete the PK
        self.public_key.delete()

        response = self.get(confirmation_key=confirmation.confirmation_key)

        # Resource not found
        self.assertEquals(404, response.status_code)
        # The confirmation is also removed automatically
        self.assertEquals(0, PublicKeyConfirmation.objects.count())

    @override_settings(TCA_CONFIRMATION_EXPIRATION_HOURS=2)
    def test_response_json(self):
        """
        Test that the view can return a JSON response.
        """
        confirmation = self.set_up_confirmation(self.public_key)
        # Sanity check: a confirmation exists
        self.assertEquals(1, PublicKeyConfirmation.objects.count())
        # Sanity check: the public key is not active
        self.assertFalse(self.public_key.active)

        response = self.get(
            confirmation_key=confirmation.confirmation_key,
            format='json')

        # Correct response?
        self.assertEquals(200, response.status_code)
        self.assertIn('application/json', response['Content-Type'])
        # Correctly rendered?
        response_content = json.loads(response.content)
        self.assertEquals(
            self.public_key.key_text,
            response_content['public_key_text'])
        self.assertTrue(response_content['url'].endswith(
            self.public_key.get_absolute_url()))
        # Correct actions?
        # The confirmation is removed
        self.assertEquals(0, PublicKeyConfirmation.objects.count())
        # The public key is enabled
        # (reload the PK from the database first)
        self.public_key = PublicKey.objects.get(pk=self.public_key.pk)
        self.assertTrue(self.public_key.active)

    @override_settings(TCA_CONFIRMATION_EXPIRATION_HOURS=2)
    @mock.patch('chat.models.timezone.now')
    def test_expired_key(self, mock_now):
        """
        Tests that the public key is not confirmed when the confirmation
        key has expired in the mean time.
        """
        mock_now.return_value = self.now
        confirmation = self.set_up_confirmation(self.public_key)
        # Rewind time forward to expire the confirmation
        mock_now.return_value = self.now + datetime.timedelta(hours=3)
        # Sanity check: a confirmation exists
        self.assertEquals(1, PublicKeyConfirmation.objects.count())
        # Sanity check: the public key is not active
        self.assertFalse(self.public_key.active)

        response = self.get(
            confirmation_key=confirmation.confirmation_key)

        self.assertEquals(404, response.status_code)
        # The confirmation is removed
        self.assertEquals(0, PublicKeyConfirmation.objects.count())
        # ...but the public key is not active
        # (reload it first)
        self.public_key = PublicKey.objects.get(pk=self.public_key.pk)
        self.assertFalse(self.public_key.active)


class MemberBasedValidationTestCase(TestCase):
    """
    Tests the :class:`MemberBasedSignatureValidationMixin`.
    """
    class MockRequest(object):
        """
        A very simple class to mock a request object that the mixin
        expects.

        There is no need to use a RequestFactory or anything of the
        sort for something this simple.
        """
        DATA = {}

    def setUp(self):
        self.mixin_instance = MemberBasedSignatureValidationMixin()
        # Attach a member instance to the mixin
        self.member = MemberFactory()
        self.mixin_instance.member = self.member
        # Attach a mock request to the mixin
        self.mixin_instance.request = self.MockRequest()
        self.stub_signature = 'This is a signature'
        self.mixin_instance.request.DATA = {
            'signature': self.stub_signature,
        }
        # Make sure the member has some active public keys
        self.active_keys = PublicKeyFactory.create_batch(
            2, member=self.member, active=True)
        # Make sure the member has some inactive public keys
        self.inactive_keys = PublicKeyFactory.create_batch(
            2, member=self.member, active=False)

    @mock.patch('chat.views.crypto.verify')
    def test_validate_signature_all_invalid(self, mock_verify):
        """
        Tests that the mixin's ``validate_signature`` method performs
        the correct steps when none of the public keys associated to
        the user yield a valid signature.
        """
        # All validation attempts will be futile
        mock_verify.return_value = False

        result = self.mixin_instance.validate_signature()

        # The result says that the message validation has failed
        self.assertFalse(result)
        # The mock was called for each valid public key
        self.assertEquals(
            len(self.active_keys),
            mock_verify.call_count)
        # Check that the calls were indeed for the valid keys
        for pubkey in self.active_keys:
            mock_verify.assert_any_call(
                self.member.lrz_id,
                self.stub_signature,
                pubkey.key_text)

    @mock.patch('chat.views.crypto.verify')
    def test_no_signature_in_request(self, mock_verify):
        """
        Make sure that a request is not considered valid if it doesn't
        even contain an appropriate signature field in the first place.
        """
        # Remove the signature field from the request
        del self.mixin_instance.request.DATA['signature']
        # It still does not consider it valid, even if the crypto.verify
        # would misbehave for None-values
        mock_verify.return_value = True

        result = self.mixin_instance.validate_signature()

        self.assertFalse(result)

    @mock.patch('chat.views.crypto.verify')
    def test_validate_signature_last_valid(self, mock_verify):
        """
        Tests that the mixin's ``validate_signature`` method performs
        the correct steps when only the last of the public keys associated to
        the user yields a valid signature.
        """
        # Set up the return value so that the last public key yields
        # a correct signature
        return_values = [False] * len(self.active_keys)
        return_values[-1] = True
        mock_verify.side_effect = return_values

        result = self.mixin_instance.validate_signature()

        self.assertTrue(result)
        # The mock was still called for each valid public key
        self.assertEquals(
            len(self.active_keys),
            mock_verify.call_count)
        # Check that the calls were indeed for the valid keys
        for pubkey in self.active_keys:
            mock_verify.assert_any_call(
                self.member.lrz_id,
                self.stub_signature,
                pubkey.key_text)

    @mock.patch('chat.views.crypto.verify')
    def test_validate_signature_first_valid(self, mock_verify):
        """
        Tests that the mixin's ``validate_signature`` method performs
        the correct steps when the first of the public keys associated to
        the user yields a valid signature.
        """
        # The first attempt to verify will already be true
        mock_verify.return_value = True

        result = self.mixin_instance.validate_signature()

        # The result says that the message validation has failed
        self.assertTrue(result)
        # The mock was called only once -- for the first valid key
        pubkey = self.active_keys[0]
        mock_verify.called_once_with(
            self.member.lrz_id,
            self.stub_signature,
            pubkey.key_text)

    def test_no_active_keys(self):
        """
        Tests that when there are no active public keys associated to
        the user, the message is not considered valid.
        """
        # Remove the active keys
        self.member.public_keys.filter(active=True).delete()
        # Sanity-check -- all public keys are no inactive
        self.assertTrue(self.member.public_keys.count() > 0)
        for pubkey in self.member.public_keys.all():
            self.assertFalse(pubkey.active)

        result = self.mixin_instance.validate_signature()

        self.assertFalse(result)


class JoinChatRoomTestCase(ViewTestCaseMixin, TestCase):
    """
    Tests the endpoint for users joining a chat room.
    """
    view_name = "chatroom-add-member"

    def setUp(self):
        self.member = MemberFactory()
        self.chat_room = ChatRoomFactory()

    @mock.patch('chat.views.ChatRoomViewSet.validate_signature')
    @mock.patch('chat.views.SystemMessage')
    def test_member_join(self, mock_system_message, mock_validate):
        """
        Tests that an existing member can join the chat room.
        """
        # Sanity check -- no members in the chat room
        self.assertEquals(0, self.chat_room.members.count())
        # Sanity check -- no messages in the chat room
        self.assertEquals(0, self.chat_room.messages.count())
        # The mock considers the signature of this message as valid
        mock_validate.return_value = True

        signature = 'This is a signature.'
        response = self.post_json({
            'lrz_id': self.member.lrz_id,
            'signature': signature,
        }, pk=self.chat_room.pk)

        # Correct actions taken?
        # Now there is a member in the chat room
        self.assertEquals(1, self.chat_room.members.count())
        # The correct member has joined?
        member = self.chat_room.members.all()[0]
        self.assertEquals(member, self.member)
        # A system message was generated for the chat room?
        mock_create = mock_system_message.objects.create_member_joined
        mock_create.assert_called_once_with(self.member, self.chat_room)
        # The system tried verifying the message signature
        mock_validate.assert_called_once_with()

        # Correct response generated?
        self.assertEquals('application/json', response['Content-Type'])
        self.assertEquals(200, response.status_code)

    @mock.patch('chat.views.ChatRoomViewSet.validate_signature')
    @mock.patch('chat.views.SystemMessage')
    def test_lrz_id_missing(self, mock_system_message, mock_validate):
        """
        Test that when an lrz_id is missing in the request, it is
        considered invalid.
        """
        # No valid key in the request
        response = self.post_json({
            'asdf': 'asdf',
        }, pk=self.chat_room.pk)

        # Correct actions taken?
        # No member in the chat room
        self.assertEquals(0, self.chat_room.members.count())
        # No system message generated
        mock_create = mock_system_message.objects.create_member_joined
        self.assertFalse(mock_create.called)
        # The system didn't try verifying anything
        self.assertFalse(mock_validate.called)

        # Correct response generated?
        self.assertEquals(400, response.status_code)

    @mock.patch('chat.views.ChatRoomViewSet.validate_signature')
    @mock.patch('chat.views.SystemMessage')
    def test_invalid_json_body(self, mock_system_message, mock_validate):
        """
        Tests that when an invalid JSON body is provided, the endpoint
        returns an appropriate response.
        """
        # No valid JSON!
        response = self.post(
            "Definitely not valid JSON", pk=self.chat_room.pk)

        # Correct actions taken?
        # No member in the chat room
        self.assertEquals(0, self.chat_room.members.count())
        # No system message generated
        mock_create = mock_system_message.objects.create_member_joined
        self.assertFalse(mock_create.called)
        # The system didn't try verifying anything
        self.assertFalse(mock_validate.called)
        # Correct response generated?
        self.assertEquals(400, response.status_code)

    @mock.patch('chat.views.ChatRoomViewSet.validate_signature')
    @mock.patch('chat.views.SystemMessage')
    def test_non_existent_lrz_id(self, mock_system_message, mock_validate):
        """
        Tests that when a non-existent lrz_id is given to the endpoint
        there are no actions taken
        """
        signature = 'Signature'

        response = self.post_json({
            'lrz_id': self.member.lrz_id + 'a',
            'signature': signature,
        }, pk=self.chat_room.pk)

        # No one is still in the chat room
        self.assertEquals(0, self.chat_room.members.count())
        # It didn't attempt to create any status message?
        mock_create = mock_system_message.objects.create_member_joined
        self.assertFalse(mock_create.called)
        # It didn't attempt to verify anything
        self.assertFalse(mock_validate.called)
        # Correct status code?
        self.assertEquals(404, response.status_code)

    @mock.patch('chat.views.ChatRoomViewSet.validate_signature')
    @mock.patch('chat.views.SystemMessage')
    def test_invalid_signature(self, mock_system_message, mock_validate):
        """
        Tests that when the request's signature is invalid, the user is not
        added to the chat room.
        """
        # Sanity check -- no members in the chat room
        self.assertEquals(0, self.chat_room.members.count())
        # Sanity check -- no messages in the chat room
        self.assertEquals(0, self.chat_room.messages.count())
        # Consider the signature as invalid
        mock_validate.return_value = False

        signature = 'This is a signature.'
        response = self.post_json({
            'lrz_id': self.member.lrz_id,
            'signature': signature,
        }, pk=self.chat_room.pk)

        # Correct actions taken?
        # Still no member in the chat room
        self.assertEquals(0, self.chat_room.members.count())
        # No message generated
        mock_create = mock_system_message.objects.create_member_joined
        self.assertFalse(mock_create.called)
        # The system tried verifying the message signature
        mock_validate.assert_called_once_with()

        # Correct response generated?
        self.assertEquals('application/json', response['Content-Type'])
        # Forbidden response status code
        self.assertEquals(403, response.status_code)
        self.assertEquals(
            'invalid signature',
            json.loads(response.content)['status'])

    @mock.patch('chat.views.ChatRoomViewSet.validate_signature')
    @mock.patch('chat.views.SystemMessage')
    def test_signature_missing(self, mock_system_message, mock_validate):
        """
        Tests the view when the signature field is missing.
        """
        response = self.post_json({
            'lrz_id': self.member.lrz_id,
        }, pk=self.chat_room.pk)

        # Correct actions taken?
        # Still no member in the chat room
        self.assertEquals(0, self.chat_room.members.count())
        # No message generated
        mock_create = mock_system_message.objects.create_member_joined
        self.assertFalse(mock_create.called)
        # The system did not try verifying the message signature
        self.assertFalse(mock_validate.called)

        # Correct response generated?
        # Invalid request response status code
        self.assertEquals(400, response.status_code)
