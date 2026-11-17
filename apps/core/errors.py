"""JSON versions of Django's own error pages, for URLs that start with /api/.

Django shows an HTML page for an unknown URL or a crash outside a DRF view.
API clients need JSON, so these handlers answer with the standard structure.
Pages outside /api/ (such as the admin site) keep Django's normal pages.
"""
from django.http import JsonResponse
from django.views import defaults

from .responses import error_payload


def _is_api(request):
    return request.path.startswith("/api/")


def _json(status_code, message, code):
    return JsonResponse(error_payload(status_code, message, code), status=status_code)


def bad_request(request, exception=None):
    if _is_api(request):
        return _json(400, "Bad request.", "bad_request")
    return defaults.bad_request(request, exception)


def permission_denied(request, exception=None):
    if _is_api(request):
        return _json(403, "You do not have permission to do this.", "forbidden")
    return defaults.permission_denied(request, exception)


def not_found(request, exception=None):
    if _is_api(request):
        return _json(404, "Not found.", "not_found")
    return defaults.page_not_found(request, exception)


def server_error(request):
    if _is_api(request):
        return _json(500, "Something went wrong on our side. Please try again later.", "server_error")
    return defaults.server_error(request)
