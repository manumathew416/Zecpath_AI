from django.http import JsonResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import JobSerializer

from .models import Job

def home(request):
    return JsonResponse({"message": "Hello Zecpath Backend"})


class JobListView(APIView):
    def get(self, request):
        jobs = Job.objects.all()
        serializer = JobSerializer(jobs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class JobCreateView(APIView):
    def post(self, request):
        serializer = JobSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserTestView(APIView):
    def get(self, request):
        return Response({"message": "User API working", "status": "ok"},
                        status=status.HTTP_200_OK)