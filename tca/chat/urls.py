from django.conf.urls import patterns
from django.conf.urls import include
from django.conf.urls import url

from rest_framework.routers import DefaultRouter
from rest_framework.routers import SimpleRouter

from chat import views

router = DefaultRouter()
# Routes which should be found in the api root
router.register(r'members', views.MemberViewSet)
router.register(r'chat_rooms', views.ChatRoomViewSet)

# Automatically generated routes, but not found in the api root
simple_router = SimpleRouter()
simple_router.register(r'chat_rooms/(?P<chat_room>[^/]+)/messages', views.ChatMessageViewSet)

urlpatterns = patterns('',
    url(r'^', include(router.urls)),
    url(r'^', include(simple_router.urls)),
)
