from django.http import JsonResponse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView


def home(request):
    return JsonResponse({"message": "Hello Zecpath Backend"})


class UserTestView(APIView):
    def get(self, request):
        return Response({"message": "User API working", "status": "ok"},
                        status=status.HTTP_200_OK)