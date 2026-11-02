from django.urls import path

from . import views

urlpatterns = [
    path("jobs/", views.JobListView.as_view(), name="job-list"),
    path("jobs/create/", views.JobCreateView.as_view(), name="job-create"),
]