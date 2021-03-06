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
simple_router.register(
    r'chat_rooms/(?P<chat_room>[^/]+)/messages',
    views.ChatMessageViewSet)
simple_router.register(
    r'members/(?P<member>[^/]+)/pubkeys',
    views.PublicKeyViewSet)

#: URLs dealing with handling Android device GCM registration IDs
registration_id_urls = (
    url(r'^members/(?P<member_id>[^/]+)/registration_ids/add_id$',
        views.AddRegistrationIdView.as_view(),
        name='add-registration-id'),
    url(r'^members/(?P<member_id>[^/]+)/registration_ids/remove_id$',
        views.RemoveRegistrationIdView.as_view(),
        name='remove-registration-id'),
)

urlpatterns = patterns('',
    url(r'^', include(router.urls)),
    url(r'^', include(simple_router.urls)),

)

urlpatterns += registration_id_urls
urlpatterns += (
    url(r'^confirmation/(?P<confirmation_key>[^/]+?)/$',
        views.PublicKeyConfirmationView.as_view(),
        name='confirmation-view'),
    url(r'^confirmation/(?P<confirmation_key>[^/]+?)/\.(?P<format>(html|json))/$',
        views.PublicKeyConfirmationView.as_view(),
        name='confirmation-view'),
)
