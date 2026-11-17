"""Day 13 - standard responses, centralized error handler and bug-fix tests.

Run with:  python manage.py test apps.core
These tests read the real JSON body that the client receives (r.json()).
"""
from unittest import mock

from django.core.cache import cache
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.accounts.models import Candidate, Role, User
from apps.jobs.models import Job

SUCCESS_KEYS = {"success", "status_code", "message", "data"}
ERROR_KEYS = {"success", "status_code", "message", "error_code", "errors"}


class Base(APITestCase):
    def setUp(self):
        cache.clear()
        self.client.raise_request_exception = False
        self.pw = "Str0ng#Pass99"
        self.admin = User.objects.create_superuser(email="admin@z.com", password=self.pw)
        self.cand = User.objects.create_user(email="c1@z.com", password=self.pw, role=Role.CANDIDATE, phone="9000000001")
        self.cand2 = User.objects.create_user(email="c2@z.com", password=self.pw, role=Role.CANDIDATE, phone="9000000002")
        self.emp = User.objects.create_user(email="e1@z.com", password=self.pw, role=Role.EMPLOYER)

    def login(self, user):
        r = self.client.post(reverse("login"), {"email": user.email, "password": self.pw})
        self.assertEqual(r.status_code, 200, r.content)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {r.json()['data']['access']}")
        return r.json()["data"]

    def assertError(self, r, status, code, message_part=None):
        body = r.json()
        self.assertEqual(r.status_code, status, body)
        self.assertEqual(set(body), ERROR_KEYS, body)
        self.assertIs(body["success"], False)
        self.assertEqual(body["status_code"], status)
        self.assertEqual(body["error_code"], code, body)
        if message_part:
            self.assertIn(message_part, body["message"] + str(body["errors"]))
        return body


class SuccessStructureTests(Base):
    def test_200_and_201_use_the_same_envelope(self):
        r = self.client.post(reverse("login"), {"email": "c1@z.com", "password": self.pw})
        body = r.json()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(set(body), SUCCESS_KEYS)
        self.assertIs(body["success"], True)
        self.assertEqual(body["status_code"], 200)
        self.assertIn("access", body["data"])

        r = self.client.post(reverse("register"), {"email": "n@z.com", "phone": "9555555555",
                                                   "password": self.pw, "role": "candidate"})
        body = r.json()
        self.assertEqual(r.status_code, 201)
        self.assertEqual(set(body), SUCCESS_KEYS)
        self.assertEqual(body["data"]["email"], "n@z.com")

    def test_204_has_no_body(self):
        self.login(self.cand)
        r = self.client.delete(reverse("candidate-profile"))
        self.assertEqual(r.status_code, 204)
        self.assertEqual(r.content, b"")

    def test_logout_message(self):
        data = self.login(self.cand)
        r = self.client.post(reverse("logout"), {"refresh": data["refresh"]})
        self.assertEqual(r.status_code, 205)

    def test_status_code_field_always_matches_http_status(self):
        self.login(self.cand)
        for method, url in [("get", reverse("job-list")), ("get", reverse("candidate-profile")),
                            ("get", reverse("me")), ("get", reverse("employer-profile")),
                            ("get", "/api/jobs/999/"), ("delete", reverse("job-list"))]:
            r = getattr(self.client, method)(url)
            self.assertEqual(r.json()["status_code"], r.status_code, (method, url))


class ErrorHandlerTests(Base):
    def test_400_validation_error(self):
        r = self.client.post(reverse("register"), {})
        body = self.assertError(r, 400, "validation_error")
        self.assertEqual(body["message"], "Validation failed.")
        self.assertIn("email", body["errors"])
        self.assertIn("password", body["errors"])

    def test_400_malformed_json(self):
        r = self.client.post(reverse("register"), '{"email": ', content_type="application/json")
        self.assertError(r, 400, "parse_error")

    def test_401_no_token_and_bad_token(self):
        self.assertError(self.client.get(reverse("job-list")), 401, "not_authenticated")
        self.client.credentials(HTTP_AUTHORIZATION="Bearer abc")
        body = self.assertError(self.client.get(reverse("job-list")), 401, "token_not_valid")
        self.assertNotIn("messages", body)                      # no internal token details

    def test_401_wrong_password(self):
        r = self.client.post(reverse("login"), {"email": "c1@z.com", "password": "wrong"})
        self.assertError(r, 401, "no_active_account")

    def test_401_from_role_middleware_uses_same_structure(self):
        self.assertError(self.client.get(reverse("admin-users")), 401, "not_authenticated")

    def test_403_permission_class_and_middleware(self):
        self.login(self.cand)
        r = self.client.post(reverse("job-create"), {"title": "x", "description": "d", "location": "k"})
        self.assertError(r, 403, "permission_denied", "Only employers")          # permission class
        self.assertError(self.client.get(reverse("admin-users")), 403, "permission_denied")   # middleware

    def test_404_variants(self):
        self.login(self.cand)
        body = self.assertError(self.client.get("/api/jobs/999/"), 404, "not_found")
        self.assertEqual(body["message"], "Not found.")          # no "No Job matches..." leak
        self.assertNotIn("Job", body["message"])
        self.client.delete(reverse("candidate-profile"))
        self.assertError(self.client.get(reverse("candidate-profile")), 404, "not_found", "Profile not found")
        self.assertError(self.client.get("/api/nothing/here/"), 404, "not_found")      # unknown URL
        self.assertError(self.client.get("/api/jobs/abc/"), 404, "not_found")          # bad id

    def test_non_api_404_keeps_normal_page(self):
        r = self.client.get("/nothing-here/")
        self.assertEqual(r.status_code, 404)
        self.assertIn("text/html", r["Content-Type"])

    def test_405(self):
        self.login(self.cand)
        self.assertError(self.client.delete(reverse("job-list")), 405, "method_not_allowed")

    def test_409_manual_response_is_wrapped(self):
        from apps.accounts.tests_resume import make_pdf, upload
        from django.test import override_settings
        import tempfile
        self.login(self.cand)
        with override_settings(MEDIA_ROOT=tempfile.mkdtemp()):
            url = reverse("candidate-resume")
            self.client.post(url, {"resume": upload("a.pdf", make_pdf())}, format="multipart")
            r = self.client.post(url, {"resume": upload("b.pdf", make_pdf())}, format="multipart")
        self.assertError(r, 409, "conflict", "already your current resume")

    def test_415_unsupported_media_type(self):
        self.login(self.cand)
        r = self.client.post(reverse("candidate-resume"), {"a": 1}, format="json")
        self.assertError(r, 415, "unsupported_media_type")

    def test_429_has_retry_time(self):
        for _ in range(6):
            r = self.client.post(reverse("login"), {"email": "c1@z.com", "password": "wrong"})
        body = self.assertError(r, 429, "throttled")
        self.assertGreater(body["errors"]["retry_after_seconds"], 0)

    def test_500_is_hidden_logged_and_in_standard_format(self):
        self.login(self.cand)
        with mock.patch("apps.jobs.views.JobListView.get_queryset", side_effect=RuntimeError("db password is hunter2")):
            with self.assertLogs("api.errors", level="ERROR") as logs:
                r = self.client.get(reverse("job-list"))
        body = self.assertError(r, 500, "server_error")
        self.assertNotIn("hunter2", r.content.decode())          # internals are never sent
        self.assertNotIn("RuntimeError", r.content.decode())
        self.assertIn("hunter2", "\n".join(logs.output))          # but the developer can see them in the log

    def test_500_outside_drf_view_is_json_for_api_urls(self):
        with mock.patch("apps.core.middleware.RoleAccessMiddleware._required_role", side_effect=RuntimeError("boom")):
            r = self.client.get("/api/admin/users/")
        self.assertError(r, 500, "server_error")


class BugFixTests(Base):
    # BUG-04 invalid phone numbers were accepted
    def test_phone_must_be_valid(self):
        for phone in ("abc", "<script>", "123", "12345678901234567", "98a76543210"):
            r = self.client.post(reverse("register"), {"email": "p@z.com", "phone": phone,
                                                       "password": self.pw, "role": "candidate"})
            self.assertEqual(r.status_code, 400, phone)
            self.assertIn("phone", r.json()["errors"])
        r = self.client.post(reverse("register"), {"email": "p@z.com", "phone": "+91 98765-43210",
                                                   "password": self.pw, "role": "candidate"})
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(User.objects.get(email="p@z.com").phone, "+919876543210")

    # BUG-07 login was case-sensitive although emails are saved in lower case
    def test_login_ignores_email_case(self):
        for email in ("C1@Z.com", "  c1@z.COM "):
            r = self.client.post(reverse("login"), {"email": email, "password": self.pw})
            self.assertEqual(r.status_code, 200, email)

    # BUG-02 a user could log out (blacklist) somebody else's refresh token
    def test_cannot_blacklist_someone_elses_token(self):
        victim = self.login(self.cand2)
        self.client.credentials()
        self.login(self.cand)
        r = self.client.post(reverse("logout"), {"refresh": victim["refresh"]})
        self.assertError(r, 403, "permission_denied", "does not belong")
        self.client.credentials()
        r = self.client.post(reverse("token-refresh"), {"refresh": victim["refresh"]})
        self.assertEqual(r.status_code, 200)                  # the victim's token still works

    def test_logout_validation(self):
        self.login(self.cand)
        self.assertError(self.client.post(reverse("logout"), {}), 400, "validation_error")
        self.assertError(self.client.post(reverse("logout"), {"refresh": "junk"}), 400, "validation_error")

    # BUG-01 the signup rate limit was never attached to the signup view
    def test_signup_is_rate_limited(self):
        codes = []
        for i in range(12):
            r = self.client.post(reverse("register"), {"email": f"s{i}@z.com", "phone": f"91000000{i:02d}",
                                                       "password": self.pw, "role": "candidate"})
            codes.append(r.status_code)
        self.assertEqual(codes[:10], [201] * 10)
        self.assertEqual(codes[10:], [429, 429])

    # BUG-03 jobs of a deactivated employer stayed visible and open for applications
    def test_deactivated_employer_jobs_are_hidden_and_closed_to_applications(self):
        job = Job.objects.create(employer=self.emp.employer_profile, title="T", description="d", location="k")
        self.login(self.cand)
        self.assertEqual(len(self.client.get(reverse("job-list")).json()["data"]["results"]), 1)
        self.emp.employer_profile.soft_delete()
        self.assertEqual(self.client.get(reverse("job-list")).json()["data"]["results"], [])
        self.assertEqual(self.client.get(reverse("job-detail", args=[job.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("apply", args=[job.pk])).status_code, 404)
        self.login(self.admin)
        self.assertEqual(self.client.get(reverse("job-detail", args=[job.pk])).status_code, 200)
        self.emp.employer_profile.restore()
        self.login(self.cand)
        self.assertEqual(len(self.client.get(reverse("job-list")).json()["data"]["results"]), 1)

