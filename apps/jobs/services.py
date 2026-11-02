from .models import Job


def get_all_jobs():
    return Job.objects.select_related("employer").all()


def get_open_jobs():
    return get_all_jobs().filter(status=Job.Status.OPEN)