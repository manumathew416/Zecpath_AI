from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import JobSerializer
from .services import get_all_jobs


class JobListView(APIView):
    def get(self, request):
        serializer = JobSerializer(get_all_jobs(), many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class JobCreateView(APIView):
    def post(self, request):
        serializer = JobSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)