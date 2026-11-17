"""Validation rules for profile data (Day 11).

Each function raises serializers.ValidationError with a clear message,
or returns the cleaned value.
"""
import re
from decimal import Decimal
from urllib.parse import urlparse

from rest_framework import serializers

MAX_SKILLS = 30
SKILL_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 .+#/&-]{0,39}$")
DOMAIN_PATTERN = re.compile(
    r"^(?=.{4,100}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$")
MAX_SALARY = Decimal("99999999")
MAX_EXPERIENCE_YEARS = 50


def clean_skills(value):
    """'python, Django ,python' -> 'python, Django' (trimmed, no duplicates)."""
    skills, seen = [], set()
    for item in value.split(","):
        item = " ".join(item.split())
        if not item:
            continue
        if not SKILL_PATTERN.match(item):
            raise serializers.ValidationError(
                f"'{item}' is not a valid skill. Use letters, numbers and . + # / & - "
                "(up to 40 characters each).")
        if item.lower() not in seen:
            seen.add(item.lower())
            skills.append(item)
    if not skills:
        raise serializers.ValidationError("Add at least one skill, separated by commas.")
    if len(skills) > MAX_SKILLS:
        raise serializers.ValidationError(f"You can add at most {MAX_SKILLS} skills.")
    return ", ".join(skills)


def clean_experience(value):
    if value < 0 or value > MAX_EXPERIENCE_YEARS:
        raise serializers.ValidationError(
            f"Experience must be between 0 and {MAX_EXPERIENCE_YEARS} years.")
    return value


def clean_expected_salary(value):
    if value is None:
        return value
    if value <= 0:
        raise serializers.ValidationError("Expected salary must be greater than 0.")
    if value > MAX_SALARY:
        raise serializers.ValidationError("Expected salary is too large.")
    return value


def clean_company_name(value):
    value = " ".join(value.split())
    if len(value) < 2:
        raise serializers.ValidationError("Company name must have at least 2 characters.")
    return value


def clean_domain(value):
    value = value.strip().lower()
    if "://" in value or "/" in value or " " in value:
        raise serializers.ValidationError(
            "Enter only the domain name, for example zecpath.com (no http:// and no path).")
    if value.startswith("www."):
        value = value[4:]
    if not DOMAIN_PATTERN.match(value):
        raise serializers.ValidationError("Enter a valid domain, for example zecpath.com.")
    return value


def website_matches_domain(website, domain):
    """The website must belong to the company's domain."""
    host = (urlparse(website).hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    return host == domain or host.endswith("." + domain)
