from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand

from intake_form.decorators import ADMIN_GROUP, PET_PARENT_GROUP, VET_GROUP


class Command(BaseCommand):
    help = "Create required RBAC groups: Admin, Vet, Pet Parent."

    def handle(self, *args, **options):
        for role in [ADMIN_GROUP, VET_GROUP, PET_PARENT_GROUP]:
            _, created = Group.objects.get_or_create(name=role)
            status = "created" if created else "already exists"
            self.stdout.write(self.style.SUCCESS(f"{role}: {status}"))
