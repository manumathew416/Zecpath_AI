from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from apps.core.permissions import IsAdmin, IsEmployer, IsJobOwner

from .models import Job
from .serializers import JobSerializer


class JobListView(generics.ListAPIView):
    """Any logged-in user can browse open jobs."""
    serializer_class = JobSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Job.objects.filter(status=Job.Status.OPEN).order_by("-posted_at")


class JobCreateView(generics.CreateAPIView):
    """Only employers can post jobs."""
    serializer_class = JobSerializer
    permission_classes = [IsEmployer]

    def perform_create(self, serializer):
        serializer.save(employer=self.request.user.employer_profile)


class JobDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Read: any logged-in user. Edit/delete: the owner employer or an admin."""
    queryset = Job.objects.all()
    serializer_class = JobSerializer
    permission_classes = [IsAuthenticated, IsJobOwner]


class EmployerJobListView(generics.ListAPIView):
    """An employer sees only their own jobs."""
    serializer_class = JobSerializer
    permission_classes = [IsEmployer]

    def get_queryset(self):
        return Job.objects.filter(employer=self.request.user.employer_profile)
