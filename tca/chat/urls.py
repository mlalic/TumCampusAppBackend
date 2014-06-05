from django.conf.urls import patterns
from django.conf.urls import include
from django.conf.urls import url

from rest_framework.routers import DefaultRouter

from chat import views

router = DefaultRouter()
# Routes which should be found in the api root
router.register(r'members', views.MemberViewSet)

urlpatterns = patterns('',
    url(r'^', include(router.urls)),
)
