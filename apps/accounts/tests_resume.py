"""Day 12 - resume upload tests.

Run with:  python manage.py test apps.accounts
Uploaded test files go to a temporary folder that is deleted afterwards.
"""
import io
import os
import shutil
import tempfile
import zipfile

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.accounts.models import Candidate, Role, User
from apps.applications.models import Application
from apps.jobs.models import Job

TEMP_MEDIA = tempfile.mkdtemp(prefix="zecpath_test_media_")


def make_pdf(extra=b"", pad=300):
    return b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\n" + extra + b"x" * pad + b"\n%%EOF\n"


def make_doc(extra=b"", pad=600):
    return b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * pad + extra


def make_docx(extra_files=None, drop=None):
    buf = io.BytesIO()
    files = {"[Content_Types].xml": "<Types/>", "word/document.xml": "<w:document/>" + "a" * 200}
    files.update(extra_files or {})
    for name in drop or []:
        files.pop(name, None)
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, content in files.items():
            z.writestr(name, content)
    return buf.getvalue()


def upload(name, data):
    return SimpleUploadedFile(name, data, content_type="application/octet-stream")


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class ResumeBase(APITestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    def setUp(self):
        cache.clear()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)      # every test starts with no files
        os.makedirs(TEMP_MEDIA, exist_ok=True)
        self.pw = "Str0ng#Pass99"
        self.admin = User.objects.create_superuser(email="admin@z.com", password=self.pw)
        self.cand = User.objects.create_user(email="c1@z.com", password=self.pw, role=Role.CANDIDATE, phone="9000000001")
        self.cand2 = User.objects.create_user(email="c2@z.com", password=self.pw, role=Role.CANDIDATE, phone="9000000002")
        self.emp = User.objects.create_user(email="e1@z.com", password=self.pw, role=Role.EMPLOYER)
        self.emp2 = User.objects.create_user(email="e2@z.com", password=self.pw, role=Role.EMPLOYER)
        self.url = reverse("candidate-resume")

    def login(self, user):
        r = self.client.post(reverse("login"), {"email": user.email, "password": self.pw})
        self.assertEqual(r.status_code, 200, r.content)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")

    def post(self, name, data):
        return self.client.post(self.url, {"resume": upload(name, data)}, format="multipart")

    def profile(self, user=None):
        return Candidate.objects.get(user=user or self.cand)

    def stored_files(self):
        found = []
        for root, _, files in os.walk(TEMP_MEDIA):
            found += [os.path.join(root, f) for f in files]
        return found


class UploadTests(ResumeBase):
    def test_upload_pdf_doc_docx(self):
        for name, data in [("cv.pdf", make_pdf()), ("cv.doc", make_doc()), ("cv.docx", make_docx())]:
            Candidate.objects.filter(user=self.cand).update(resume="", resume_hash="")
            self.login(self.cand)
            r = self.post(name, data)
            self.assertIn(r.status_code, (200, 201), (name, r.content))

    def test_first_upload_201_and_server_naming_standard(self):
        self.login(self.cand)
        r = self.post("My Resume (final).pdf", make_pdf())
        self.assertEqual(r.status_code, 201, r.content)
        p = self.profile()
        self.assertRegex(p.resume.name, rf"^resumes/candidate_{p.pk}/resume_\d{{8}}-\d{{6}}_[0-9a-f]{{8}}\.pdf$")
        self.assertEqual(p.resume_original_name, "My Resume (final).pdf")
        self.assertEqual(p.resume_size, len(make_pdf()))
        self.assertEqual(len(p.resume_hash), 64)

    def test_user_filename_never_used_for_storage(self):
        self.login(self.cand)
        r = self.post("../../evil name.pdf", make_pdf())
        self.assertEqual(r.status_code, 201)
        p = self.profile()
        self.assertNotIn("evil", p.resume.name)
        self.assertTrue(os.path.realpath(p.resume.path).startswith(os.path.realpath(TEMP_MEDIA)))
        self.assertEqual(p.resume_original_name, "evil name.pdf")      # cleaned, no folders

    def test_no_file_sent(self):
        self.login(self.cand)
        r = self.client.post(self.url, {}, format="multipart")
        self.assertEqual(r.status_code, 400)


class SecurityValidationTests(ResumeBase):
    def setUp(self):
        super().setUp()
        self.login(self.cand)

    def assertRejected(self, name, data, fragment=None):
        r = self.post(name, data)
        self.assertEqual(r.status_code, 400, (name, r.content))
        if fragment:
            self.assertIn(fragment, str(r.data))
        self.assertEqual(self.stored_files(), [])           # nothing was saved
        self.assertFalse(self.profile().resume)

    def test_wrong_extensions(self):
        for name in ("cv.exe", "cv.png", "cv.txt", "cv.html", "cv.php", "cv", "cv.pdf.exe", "cv.zip"):
            self.assertRejected(name, make_pdf(), "Only PDF, DOC and DOCX")

    def test_fake_files_with_allowed_extension(self):
        self.assertRejected("cv.pdf", b"MZ" + b"\x00" * 400, "not a real PDF")          # exe renamed
        self.assertRejected("cv.pdf", b"<html><script>alert(1)</script></html>" * 10, "not a real PDF")
        self.assertRejected("cv.doc", make_pdf(), "not a real .doc")                    # wrong content
        self.assertRejected("cv.docx", make_pdf(), "not a real .docx")
        self.assertRejected("cv.pdf", make_docx(), "not a real PDF")

    def test_empty_and_truncated(self):
        self.assertRejected("cv.pdf", b"", "empty or too small")
        self.assertRejected("cv.pdf", b"%PDF-1.4 " + b"x" * 300, "incomplete")

    def test_size_limit(self):
        big = make_pdf(pad=5 * 1024 * 1024)
        self.assertRejected("cv.pdf", big, "too large")
        ok = make_pdf(pad=4 * 1024 * 1024)
        self.assertEqual(self.post("cv.pdf", ok).status_code, 201)

    def test_pdf_with_scripts_or_embedded_files(self):
        for bad in (b"/JavaScript (app.alert(1))", b"/JS (x)", b"/Launch /Win", b"/Type /EmbeddedFile >>",
                    b"/S /J#61vaScr#69pt"):                  # last one hides the word with hex escapes
            self.assertRejected("cv.pdf", make_pdf(bad + b" "), "scripts")
        self.assertEqual(self.post("ok.pdf", make_pdf(b"/Type /Page /JSON-not-a-script ")).status_code, 201)

    def test_docx_with_macros_or_bad_structure(self):
        self.assertRejected("cv.docx", make_docx({"word/vbaProject.bin": "x"}), "macros")
        self.assertRejected("cv.docx", make_docx({"word/activeX/a.xml": "x"}), "macros")
        self.assertRejected("cv.docx", make_docx(drop=["word/document.xml"]), "not a valid Word")
        self.assertRejected("cv.docx", make_docx({"../../evil.txt": "x"}), "unsafe")
        self.assertRejected("cv.docx", b"PK\x03\x04" + b"junk" * 100, "damaged")

    def test_zip_bomb(self):
        bomb = make_docx({"word/big.xml": "0" * (60 * 1024 * 1024)})
        self.assertLess(len(bomb), 5 * 1024 * 1024)          # small on upload, huge when opened
        self.assertRejected("cv.docx", bomb, "too complex or too large")

    def test_doc_with_macros(self):
        self.assertRejected("cv.doc", make_doc("_VBA_PROJECT".encode("utf-16-le")), "macros")


class DuplicateAndReplaceTests(ResumeBase):
    def setUp(self):
        super().setUp()
        self.login(self.cand)

    def test_same_file_twice_is_409_and_not_stored_twice(self):
        self.assertEqual(self.post("a.pdf", make_pdf()).status_code, 201)
        r = self.post("renamed.pdf", make_pdf())               # same content, new name
        self.assertEqual(r.status_code, 409)
        self.assertEqual(len(self.stored_files()), 1)

    def test_replacement_removes_old_file(self):
        self.post("a.pdf", make_pdf())
        old = self.profile().resume.name
        r = self.post("b.docx", make_docx())
        self.assertEqual(r.status_code, 200)                  # replaced
        p = self.profile()
        self.assertNotEqual(p.resume.name, old)
        self.assertTrue(p.resume.name.endswith(".docx"))
        self.assertEqual(p.resume_original_name, "b.docx")
        files = self.stored_files()
        self.assertEqual(len(files), 1)
        self.assertEqual(os.path.basename(files[0]), os.path.basename(p.resume.name))

    def test_failed_replacement_keeps_old_resume(self):
        self.post("a.pdf", make_pdf())
        before = self.profile().resume.name
        self.assertEqual(self.post("bad.exe", b"MZ" * 200).status_code, 400)
        self.assertEqual(self.profile().resume.name, before)
        self.assertEqual(len(self.stored_files()), 1)

    def test_view_and_delete(self):
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.post("a.pdf", make_pdf())
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["name"], "a.pdf")
        self.assertEqual(self.client.delete(self.url).status_code, 204)
        self.assertEqual(self.stored_files(), [])
        self.assertFalse(self.profile().resume)
        self.assertEqual(self.client.delete(self.url).status_code, 404)

    def test_profile_shows_resume(self):
        self.assertIsNone(self.client.get(reverse("candidate-profile")).data["resume"])
        self.post("a.pdf", make_pdf())
        resume = self.client.get(reverse("candidate-profile")).data["resume"]
        self.assertEqual(resume["name"], "a.pdf")
        self.assertEqual(resume["download_url"], "/api/candidate/resume/download/")

    def test_deleted_profile_cannot_upload(self):
        self.client.delete(reverse("candidate-profile"))
        self.assertEqual(self.post("a.pdf", make_pdf()).status_code, 404)

    def test_upload_rate_limit(self):
        codes = [self.post(f"{i}.pdf", make_pdf(pad=300 + i)).status_code for i in range(12)]
        self.assertEqual(codes.count(429), 2)


class SecureAccessTests(ResumeBase):
    def setUp(self):
        super().setUp()
        self.login(self.cand)
        self.data = make_pdf(pad=500)
        self.post("my cv.pdf", self.data)
        self.job = Job.objects.create(employer=self.emp.employer_profile, title="T", description="d", location="k")
        self.app = Application.objects.create(job=self.job, candidate=self.profile())

    def test_candidate_downloads_own_with_safe_headers(self):
        r = self.client.get(reverse("candidate-resume-download"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(b"".join(r.streaming_content), self.data)
        self.assertEqual(r["Content-Type"], "application/pdf")
        self.assertIn("attachment", r["Content-Disposition"])
        self.assertIn("my cv.pdf", r["Content-Disposition"])
        self.assertEqual(r["X-Content-Type-Options"], "nosniff")
        self.assertIn("no-store", r["Cache-Control"])

    def test_no_public_media_url(self):
        self.assertEqual(self.client.get("/media/" + self.profile().resume.name).status_code, 404)
        self.client.credentials()
        self.assertEqual(self.client.get(reverse("candidate-resume-download")).status_code, 401)

    def test_candidates_only_reach_their_own_resume(self):
        self.login(self.cand2)
        self.assertEqual(self.client.get(reverse("candidate-resume-download")).status_code, 404)

    def test_employer_of_the_job_can_download(self):
        self.login(self.emp)
        r = self.client.get(reverse("application-resume", args=[self.app.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(b"".join(r.streaming_content), self.data)

    def test_other_employer_cannot_download(self):
        self.login(self.emp2)
        self.assertEqual(self.client.get(reverse("application-resume", args=[self.app.pk])).status_code, 404)

    def test_wrong_roles_blocked(self):
        for url in (reverse("application-resume", args=[self.app.pk]),):
            self.login(self.cand)
            self.assertEqual(self.client.get(url).status_code, 403)
        admin_url = reverse("admin-candidate-resume", args=[self.profile().pk])
        for u in (self.cand, self.emp):
            self.login(u)
            self.assertEqual(self.client.get(admin_url).status_code, 403)
            self.assertEqual(self.client.delete(admin_url).status_code, 403)
        self.login(self.emp)
        self.assertEqual(self.client.post(self.url, {"resume": upload("a.pdf", make_pdf())},
                                          format="multipart").status_code, 403)

    def test_deleted_candidate_resume_hidden_from_employer(self):
        self.login(self.cand)
        self.client.delete(reverse("candidate-profile"))
        self.login(self.emp)
        self.assertEqual(self.client.get(reverse("application-resume", args=[self.app.pk])).status_code, 404)

    def test_admin_can_download_and_remove(self):
        self.login(self.admin)
        url = reverse("admin-candidate-resume", args=[self.profile().pk])
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(b"".join(r.streaming_content), self.data)
        self.assertEqual(self.client.delete(url).status_code, 204)
        self.assertEqual(self.stored_files(), [])
        self.assertEqual(self.client.get(url).status_code, 404)
