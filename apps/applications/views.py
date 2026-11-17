from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics, status
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.exceptions import NotFound
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.resume_views import serve_resume
from apps.core.permissions import IsCandidate, IsEmployer
from apps.jobs.models import Job

from .filters import ApplicationFilter
from .models import Application
from .serializers import (
    ApplicantSerializer, ApplicationSerializer, ApplicationStatusSerializer)


class ApplyView(APIView):
    """Only candidates can apply, and only once per open job."""
    permission_classes = [IsCandidate]

    def post(self, request, job_id):
        job = get_object_or_404(Job, pk=job_id, status=Job.Status.OPEN,
                                employer__is_deleted=False)
        candidate = request.user.candidate_profile
        if candidate.is_deleted:
            raise PermissionDenied("Your candidate profile is deactivated.")
        application, created = Application.objects.get_or_create(job=job, candidate=candidate)
        if not created:
            return Response({"detail": "You have already applied to this job."},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(ApplicationSerializer(application).data, status=status.HTTP_201_CREATED)


class MyApplicationsView(generics.ListAPIView):
    """A candidate sees only their own applications.

    Filters  ?status=shortlisted &applied_after=2026-11-01 &applied_before=2026-11-30
    Search   ?search=django        (job title, job location or company name)
    Ordering ?ordering=-applied_at | status
    """
    serializer_class = ApplicationSerializer
    permission_classes = [IsCandidate]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = ApplicationFilter
    search_fields = ["job__title", "job__location", "job__employer__company_name"]
    ordering_fields = ["applied_at", "status"]
    ordering = ["-applied_at", "-id"]

    def get_queryset(self):
        # select_related: job title and company name come in the same query.
        # Without it, every row would run 2 more queries (the N+1 problem).
        return (Application.objects
                .filter(candidate=self.request.user.candidate_profile)
                .select_related("job__employer"))


class JobApplicantsView(generics.ListAPIView):
    """An employer sees applicants only for their own jobs.

    Filters  ?status=applied &min_score=60 &max_score=90 &applied_after=... &applied_before=...
    Search   ?search=python        (candidate skills, location or email)
    Ordering ?ordering=-ats_score | applied_at
    """
    serializer_class = ApplicantSerializer
    permission_classes = [IsEmployer]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = ApplicationFilter
    search_fields = ["candidate__skills", "candidate__location", "candidate__user__email"]
    ordering_fields = ["ats_score", "applied_at", "status"]
    ordering = ["-applied_at", "-id"]

    def get_queryset(self):
        job = get_object_or_404(Job, pk=self.kwargs["job_id"],
                                employer=self.request.user.employer_profile)
        # candidates who deactivated their profile are not shown to employers
        return (job.applications
                .filter(candidate__is_deleted=False)
                .select_related("candidate__user"))


class ApplicationStatusView(generics.UpdateAPIView):
    """An employer can shortlist/reject/hire, only for applications to their own jobs."""
    serializer_class = ApplicationStatusSerializer
    permission_classes = [IsEmployer]
    http_method_names = ["patch"]

    def get_queryset(self):
        return Application.objects.filter(job__employer=self.request.user.employer_profile)

class ApplicationResumeView(APIView):
    """An employer can download the resume only of someone who applied to
    one of their own jobs."""
    permission_classes = [IsEmployer]

    def get(self, request, pk):
        application = get_object_or_404(
            Application.objects.select_related("candidate"),
            pk=pk, job__employer=request.user.employer_profile)
        if application.candidate.is_deleted:
            raise NotFound("Candidate not found.")
        return serve_resume(application.candidate)
