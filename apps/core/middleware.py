"""Role middleware.

Runs before the view. It reads the JWT, finds the user, and blocks a whole
URL area (for example /api/admin/) for the wrong role. This is a second
safety net. The permission classes on each view remain the main check.
"""
import logging

from django.http import JsonResponse
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed, InvalidToken

from apps.accounts.models import Role

logger = logging.getLogger("security")

# URL prefix -> the only role allowed inside it
ROLE_PREFIXES = {
    "/api/admin/": Role.ADMIN,
    "/api/employer/": Role.EMPLOYER,
    "/api/candidate/": Role.CANDIDATE,
}


class RoleAccessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.jwt = JWTAuthentication()

    def __call__(self, request):
        required = self._required_role(request.path)
        if required:
            try:
                result = self.jwt.authenticate(request)
            except (InvalidToken, AuthenticationFailed):
                result = None

            if result is None:
                logger.warning("401 no/invalid token: %s %s", request.method, request.path)
                return JsonResponse({"detail": "Authentication required."}, status=401)

            user, _ = result
            if user.role != required:
                logger.warning(
                    "403 role violation: user=%s role=%s tried %s %s",
                    user.email, user.role, request.method, request.path,
                )
                return JsonResponse(
                    {"detail": f"This area is for {required} accounts only."}, status=403
                )
            request.role = user.role

        return self.get_response(request)

    @staticmethod
    def _required_role(path):
        for prefix, role in ROLE_PREFIXES.items():
            if path.startswith(prefix):
                return role
        return None
