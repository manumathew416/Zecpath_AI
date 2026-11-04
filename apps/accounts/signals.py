from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Candidate, Employer, Role, User


@receiver(post_save, sender=User)
def create_or_sync_profile(sender, instance, created, **kwargs):
    if created:
        # auto-create the profile that matches the role
        if instance.role == Role.CANDIDATE:
            Candidate.objects.create(user=instance, phone=instance.phone)
        elif instance.role == Role.EMPLOYER:
            Employer.objects.create(
                user=instance, is_verified=instance.is_verified)
    else:
        # profile sync: keep shared fields in step with the user
        if instance.role == Role.EMPLOYER:
            Employer.objects.filter(user=instance).update(
                is_verified=instance.is_verified)
        elif instance.role == Role.CANDIDATE:
            Candidate.objects.filter(user=instance).update(
                phone=instance.phone)