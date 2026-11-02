def skills_to_list(text):
    """Turn 'Python, Django ,REST' into ['python', 'django', 'rest']."""
    return [s.strip().lower() for s in text.split(",") if s.strip()]