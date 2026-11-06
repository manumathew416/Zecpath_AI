from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.serializers import UserSerializer
from apps.core.permissions import IsAdmin


class AdminUserListView(generics.ListAPIView):
    """Admin can see every user."""
    queryset = User.objects.all().order_by("id")
    serializer_class = UserSerializer
    permission_classes = [IsAdmin]


class AdminUserActiveView(APIView):
    """Admin can block or unblock a user (is_active)."""
    permission_classes = [IsAdmin]

    def patch(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        if user.pk == request.user.pk:
            return Response({"detail": "You cannot block your own account."},
                            status=status.HTTP_400_BAD_REQUEST)
        user.is_active = bool(request.data.get("is_active", True))
        user.save(update_fields=["is_active"])
        return Response({"id": user.pk, "is_active": user.is_active})
