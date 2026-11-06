from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsCandidate, IsEmployer
from apps.jobs.models import Job

from .models import Application
from .serializers import ApplicationSerializer, ApplicationStatusSerializer


class ApplyView(APIView):
    """Only candidates can apply, and only once per open job."""
    permission_classes = [IsCandidate]

    def post(self, request, job_id):
        job = get_object_or_404(Job, pk=job_id, status=Job.Status.OPEN)
        candidate = request.user.candidate_profile
        application, created = Application.objects.get_or_create(job=job, candidate=candidate)
        if not created:
            return Response({"detail": "You have already applied to this job."},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(ApplicationSerializer(application).data, status=status.HTTP_201_CREATED)


class MyApplicationsView(generics.ListAPIView):
    """A candidate sees only their own applications."""
    serializer_class = ApplicationSerializer
    permission_classes = [IsCandidate]

    def get_queryset(self):
        return Application.objects.filter(candidate=self.request.user.candidate_profile)


class JobApplicantsView(generics.ListAPIView):
    """An employer sees applicants only for their own jobs."""
    serializer_class = ApplicationSerializer
    permission_classes = [IsEmployer]

    def get_queryset(self):
        job = get_object_or_404(Job, pk=self.kwargs["job_id"],
                                employer=self.request.user.employer_profile)
        return job.applications.all()


class ApplicationStatusView(generics.UpdateAPIView):
    """An employer can shortlist/reject/hire, only for applications to their own jobs."""
    serializer_class = ApplicationStatusSerializer
    permission_classes = [IsEmployer]
    http_method_names = ["patch"]

    def get_queryset(self):
        return Application.objects.filter(job__employer=self.request.user.employer_profile)