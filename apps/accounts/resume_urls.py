from django.urls import path

from . import resume_views as v

urlpatterns = [
    path("candidate/resume/", v.CandidateResumeView.as_view(), name="candidate-resume"),
    path("candidate/resume/download/", v.CandidateResumeDownloadView.as_view(), name="candidate-resume-download"),
    path("admin/candidates/<int:pk>/resume/", v.AdminCandidateResumeView.as_view(), name="admin-candidate-resume"),
]
