"""
Module contains the implementation of various notifiers handling
notifying users of newly sent messages.
"""

from django.conf import settings

from gcm import GCM
import json

from rest_framework.renderers import JSONRenderer

from chat.serializers import ListMessageSerializer


class NotifierMeta(type):
    """
    The metaclass for all message notifier classes.

    Provides a way to automatically register all subclasses so that they can
    be referenced when necessary to find all implemented notifiers.
    """
    def __init__(cls, name, bases, attrs):
        if not hasattr(cls, 'notifiers'):
            cls.notifiers = []
        else:
            cls.notifiers.append(cls)

        cls.unregister_notifier = classmethod(
            lambda cls: cls.notifiers.remove(cls)
        )


class BaseNotifier(object):
    """
    The base class for all notifiers.

    In order to be a valid notifier class, subclasses need to implement the
    classmethods ``get_instance`` and ``is_enabled``, as well as a method
    ``notify``.

    All subclasses are automatically registered as notifier classes, so to
    provide an additional notification method, it is enough simply to subclass
    this base class.
    """
    __metaclass__ = NotifierMeta

    @classmethod
    def get_instance(cls):
        """
        Classmethod needs to provide an instance of the notifier which
        can be used to send a notification.

        This way we let each notifier implementation provide their own
        initialization based on the global settings of the Django project.
        """
        raise NotImplementedError

    @classmethod
    def is_enabled(cls):
        """
        Lets a notifier implementation provide the information on whether
        it should be enabled, i.e. whether it should be provided in the list
        of all notifiers returned by :func:`get_notifiers`
        """
        raise NotImplementedError

    def notify(self, message):
        """
        All concrete notifiers need to implement this method
        """
        raise NotImplementedError


def get_notifiers():
    """
    Function returns a list of all instances of all enabled notifier
    implementations.
    """
    return tuple(
        notifier_class.get_instance()
        for notifier_class in BaseNotifier.notifiers
        if notifier_class.is_enabled()
    )


class GcmNotifier(BaseNotifier):
    """
    Google Cloud Messaging notifications for new messages.
    """

    def __init__(self, api_key):
        self._gcm = GCM(api_key)

    @classmethod
    def get_instance(cls):
        return cls(settings.TCA_GCM_API_KEY)

    @classmethod
    def is_enabled(cls):
        return settings.TCA_ENABLE_GCM_NOTIFICATIONS

    def notify(self, message):
        """
        Sends a notification to all members of the chat group to which
        the given message was posted.

        It makes sure to send only a single request off to the GCM servers
        by batching all ``registration_id`` together in the request.
        """
        # Batch the registraion IDs to which a notification is to be sent
        registration_ids = self._get_registration_ids(message)
        if len(registration_ids) == 0:
            # No need to do anything if there's no one to send the notification
            # to
            return
        # Obtain the data to be sent
        data = self._message_to_data(message)

        # Finally perform the send request
        self._send_request(registration_ids, data)

    def _get_registration_ids(self, message):
        # Get all members apart from the sender themselves
        members = message.chat_room.members.exclude(pk=message.member.pk)

        # Batch all of their registration_ids
        registration_ids = []
        for member in members:
            registration_ids.extend(member.registration_ids)

        return registration_ids

    def _message_to_data(self, message):
        """
        Converts the given :class:`chat.models.Message` instance to a Python
        dict suitable to be transferred in the GCM notification.
        """
        # Leverage the MessageSerializer to get the serialized representation
        # of a Message
        serializer = ListMessageSerializer(message)

        json_message = JSONRenderer().render(serializer.data)

        # Convert the JSON back to a dict so that the GCM package can
        # correctly handle the request
        return json.loads(json_message)

    def _send_request(self, registration_ids, data):
        """
        Sends the notification to GCM servers where the registration ids
        are set to the ones given as the parameter.

        :param registration_ids: A list of registration IDs which are to
            receive the notification
        :param data: The data which is to be included in the notification
            as a Python dict
        """
        try:
            response = self._gcm.json_request(
                registration_ids=registration_ids,
                data=data)
        except:
            # Gotta catch 'em all!
            pass
