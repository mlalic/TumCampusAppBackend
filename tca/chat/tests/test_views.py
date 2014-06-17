from django.test import TestCase

from django.core.urlresolvers import reverse
from urllib import urlencode

import json

from chat.models import Member
from chat.models import Message
from chat.models import ChatRoom

from .factories import MemberFactory
from .factories import MessageFactory
from .factories import ChatRoomFactory


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
        'first_name',
        'last_name',
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

    def test_create_message(self):
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