from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("api/users/test/", views.UserTestView.as_view(), name="user-test"),
]