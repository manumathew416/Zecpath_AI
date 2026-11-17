from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics, status
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.filters import UserFilter
from apps.accounts.models import User
from apps.accounts.serializers import UserSerializer
from apps.core.permissions import IsAdmin


class AdminUserListView(generics.ListAPIView):
    """Admin can see every user.

    Filters  ?role=employer &is_active=false &is_verified=true
             &joined_after=2026-11-01 &joined_before=2026-11-30
    Search   ?search=gmail.com     (email or phone)
    Ordering ?ordering=-created_at | email | id
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAdmin]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = UserFilter
    search_fields = ["email", "phone"]
    ordering_fields = ["id", "email", "created_at"]
    ordering = ["id"]


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
