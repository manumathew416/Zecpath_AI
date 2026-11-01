from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('api/jobs/', views.JobListView.as_view(), name='job-list'),
    path('api/jobs/create/', views.JobCreateView.as_view(), name='job-create'),
    path('api/users/test/', views.UserTestView.as_view(), name='user-test'),
]