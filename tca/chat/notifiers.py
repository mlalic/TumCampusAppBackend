"""
Module contains the implementation of various notifiers handling
notifying users of newly sent messages.
"""

from django.conf import settings


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
