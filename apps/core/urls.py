from django.urls import path

from . import views
from . import admin_views

urlpatterns = [
    path("", views.home, name="home"),
    path("api/users/test/", views.UserTestView.as_view(), name="user-test"),
    path("api/admin/users/", admin_views.AdminUserListView.as_view(), name="admin-users"),
    path("api/admin/users/<int:pk>/active/", admin_views.AdminUserActiveView.as_view(), name="admin-user-active"),
] 