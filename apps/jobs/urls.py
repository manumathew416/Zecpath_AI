from django.urls import path

from . import views

urlpatterns = [
    path("jobs/", views.JobListView.as_view(), name="job-list"),
    path("jobs/create/", views.JobCreateView.as_view(), name="job-create"),
    path("jobs/<int:pk>/", views.JobDetailView.as_view(), name="job-detail"),
    path("employer/jobs/", views.EmployerJobListView.as_view(), name="employer-jobs"),
]
