"""
Module containing factory_boy factories for the models of the
:mod:`chat` app.
"""
from chat.models import Member

import factory.fuzzy
import factory


class MemberFactory(factory.DjangoModelFactory):
    """
    A factory of :class:`chat.models.Member` objects.

    By default it returns a completely random member.
    """
    FACTORY_FOR = Member

    lrz_id = factory.fuzzy.FuzzyText(length=7)
    first_name = factory.fuzzy.FuzzyText()
    last_name = factory.fuzzy.FuzzyText()
