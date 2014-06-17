"""
Module containing factory_boy factories for the models of the
:mod:`chat` app.
"""
from chat.models import Member
from chat.models import Message
from chat.models import ChatRoom

import factory.fuzzy
import factory
import random


class FuzzyForeignKeyChoice(factory.fuzzy.BaseFuzzyAttribute):
    """
    A custom FuzzyAttribute for factory_boy which choses a random instance
    of a model for a new instance's field value.
    """
    def __init__(self, model):
        self.model = model

    def get_queryset(self):
        """
        Return a query set of instances of the given model.

        By default returns a queryset representing all instances.
        """
        return self.model.objects.all()

    def fuzz(self):
        # At the moment of fuzzying the field, obtain a query set of the
        # given model and return a random value
        return random.choice(list(self.get_queryset()))


class MemberFactory(factory.DjangoModelFactory):
    """
    A factory of :class:`chat.models.Member` objects.

    By default it returns a completely random member.
    """
    FACTORY_FOR = Member

    lrz_id = factory.fuzzy.FuzzyText(length=7)
    first_name = factory.fuzzy.FuzzyText()
    last_name = factory.fuzzy.FuzzyText()


class ChatRoomFactory(factory.DjangoModelFactory):
    """
    A factory of :class:`chat.models.ChatRoom` objects.

    By default it creates a completely random chat room with no members.
    """
    FACTORY_FOR = ChatRoom

    name = factory.fuzzy.FuzzyText()


class MessageFactory(factory.DjangoModelFactory):
    """
    A factory of :class:`chat.models.ChatRoom` objects.

    By default it creates a message with a random text created by a random
    existing member in a random chat room.
    """
    FACTORY_FOR = Message

    text = factory.fuzzy.FuzzyText()
    member = FuzzyForeignKeyChoice(Member)
    chat_room = FuzzyForeignKeyChoice(ChatRoom)
