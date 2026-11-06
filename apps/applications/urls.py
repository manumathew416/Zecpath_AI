from django.urls import path

from . import views

urlpatterns = [
    path("jobs/<int:job_id>/apply/", views.ApplyView.as_view(), name="apply"),
    path("candidate/applications/", views.MyApplicationsView.as_view(), name="my-applications"),
    path("employer/jobs/<int:job_id>/applicants/", views.JobApplicantsView.as_view(), name="job-applicants"),
    path("employer/applications/<int:pk>/status/", views.ApplicationStatusView.as_view(), name="application-status"),
]
