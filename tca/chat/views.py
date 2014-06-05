from django.shortcuts import render

from rest_framework import viewsets

from chat.models import Member
from chat.serializers import MemberSerializer


class MemberViewSet(viewsets.ModelViewSet):
    model = Member
    serializer_class = MemberSerializer
