"""Resume upload checks (Day 12).

validate_resume_file() raises a 400 error with a clear message when a file
is not acceptable, and returns details about the file when it is.
"""
import hashlib
import io
import os
import re
import zipfile

from django.conf import settings
from rest_framework import serializers

ALLOWED_TYPES = {
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
MAX_SIZE = getattr(settings, "RESUME_MAX_SIZE", 5 * 1024 * 1024)      # 5 MB
MIN_SIZE = 100                                                        # bytes

OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"      # start of a real .doc file
ZIP_MAGIC = b"PK\x03\x04"                            # start of a real .docx file
PDF_MAGIC = b"%PDF-"

# PDF features that run code or hide files inside the PDF
PDF_ACTIVE = re.compile(rb"/(JavaScript|JS|Launch|EmbeddedFile|RichMedia)(?![A-Za-z0-9])")
HEX_ESCAPE = re.compile(rb"#([0-9A-Fa-f]{2})")       # PDF lets /JavaScript be written /J#61vaScript
# old .doc macros live in a stream called _VBA_PROJECT (stored as UTF-16)
DOC_MACRO = "_VBA_PROJECT".encode("utf-16-le")

MAX_ZIP_ENTRIES = 2000
MAX_UNZIPPED = 50 * 1024 * 1024                      # blocks zip bombs


def get_extension(name):
    return os.path.splitext(name or "")[1].lower()


def clean_original_name(name, ext):
    """Safe display name: no folders, no strange characters, max 100 chars."""
    base = os.path.basename((name or "").replace("\\", "/"))
    stem = os.path.splitext(base)[0]
    stem = re.sub(r"[^A-Za-z0-9 ._()-]", "", stem)
    stem = " ".join(stem.split())[:100].strip(" .")
    return (stem or "resume") + ext


def _fail(message):
    raise serializers.ValidationError({"resume": [message]})


def _check_pdf(data):
    if not data.startswith(PDF_MAGIC):
        _fail("The file content is not a real PDF.")
    if b"%%EOF" not in data[-4096:]:
        _fail("The PDF looks incomplete or damaged.")
    plain = HEX_ESCAPE.sub(lambda m: bytes([int(m.group(1), 16)]), data)
    if PDF_ACTIVE.search(plain):
        _fail("PDFs with scripts, launch actions or embedded files are not allowed.")


def _check_doc(data):
    if not data.startswith(OLE_MAGIC):
        _fail("The file content is not a real .doc document.")
    if DOC_MACRO in data:
        _fail("Documents with macros are not allowed.")


def _check_docx(data):
    if not data.startswith(ZIP_MAGIC):
        _fail("The file content is not a real .docx document.")
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        _fail("The .docx file is damaged.")
    infos = archive.infolist()
    names = [i.filename for i in infos]
    if len(names) > MAX_ZIP_ENTRIES or sum(i.file_size for i in infos) > MAX_UNZIPPED:
        _fail("The document is too complex or too large when opened.")
    for name in names:
        if name.startswith(("/", "\\")) or ".." in name.replace("\\", "/").split("/"):
            _fail("The document contains unsafe file paths.")
    lowered = [n.lower() for n in names]
    if "[content_types].xml" not in lowered or "word/document.xml" not in lowered:
        _fail("The file is not a valid Word document.")
    if any(n.endswith("vbaproject.bin") or n.startswith("word/activex/") for n in lowered):
        _fail("Documents with macros or ActiveX content are not allowed.")


CHECKS = {".pdf": _check_pdf, ".doc": _check_doc, ".docx": _check_docx}


def validate_resume_file(upload):
    ext = get_extension(upload.name)
    if ext not in ALLOWED_TYPES:
        _fail("Only PDF, DOC and DOCX files are allowed.")
    if upload.size < MIN_SIZE:
        _fail("The file is empty or too small.")
    if upload.size > MAX_SIZE:
        _fail(f"The file is too large. The maximum size is {MAX_SIZE // (1024 * 1024)} MB.")

    upload.seek(0)
    data = upload.read()
    upload.seek(0)

    CHECKS[ext](data)           # content must match the extension, no active content

    return {
        "ext": ext,
        "size": len(data),
        "hash": hashlib.sha256(data).hexdigest(),
        "original_name": clean_original_name(upload.name, ext),
    }


def describe_resume(profile, download_url=None):
    """Small summary of the stored resume, or None."""
    if not profile.resume:
        return None
    return {
        "name": profile.resume_original_name,
        "size": profile.resume_size,
        "uploaded_at": profile.resume_uploaded_at,
        "download_url": download_url,
    }
