"""Custom permission classes for Role-Based Access Control (RBAC).

Every class checks two things: the user is logged in (and active), and the
user's role matches. The role comes from the database user, not from the
request body, so a client cannot choose its own role.
"""
from rest_framework.permissions import SAFE_METHODS, BasePermission

from apps.accounts.models import Role


class HasRole(BasePermission):
    """Base class: subclasses set `allowed_role`."""

    allowed_role = None
    message = "You do not have permission to perform this action."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and user.role == self.allowed_role
        )


class IsAdmin(HasRole):
    allowed_role = Role.ADMIN
    message = "Admin access required."


class IsEmployer(HasRole):
    allowed_role = Role.EMPLOYER
    message = "Only employers can do this."


class IsCandidate(HasRole):
    allowed_role = Role.CANDIDATE
    message = "Only candidates can do this."


class IsJobOwner(BasePermission):
    """Object-level rule: an employer may change only their own jobs.
    Anyone logged in can read (SAFE_METHODS); admin can do everything."""

    message = "You can only manage your own jobs."

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        if request.user.role == Role.ADMIN:
            return True
        return obj.employer.user_id == request.user.id
