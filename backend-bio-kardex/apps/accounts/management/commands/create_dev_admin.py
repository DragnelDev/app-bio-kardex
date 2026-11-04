from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import Rol, Usuario


class Command(BaseCommand):
    help = "Crea el usuario administrador definido en el entorno de desarrollo."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Este comando solo se permite cuando DEBUG=True.")

        username = settings.DEV_ADMIN_USERNAME
        email = settings.DEV_ADMIN_EMAIL
        password = settings.DEV_ADMIN_PASSWORD
        if not password:
            raise CommandError(
                "Configura DEV_ADMIN_PASSWORD en el archivo .env antes de continuar."
            )

        existing_user = Usuario.objects.filter(username=username).first()
        if existing_user:
            if existing_user.is_superuser:
                self.stdout.write(
                    self.style.WARNING(
                        f"El superusuario '{username}' ya existe; no se realizaron cambios."
                    )
                )
                return
            raise CommandError(
                f"El usuario '{username}' ya existe y no es superusuario."
            )

        user = Usuario(username=username, email=email, rol=Rol.ADMIN)
        try:
            validate_password(password, user)
        except ValidationError as error:
            raise CommandError("; ".join(error.messages)) from error

        Usuario.objects.create_superuser(
            username=username,
            email=email,
            password=password,
            rol=Rol.ADMIN,
        )
        self.stdout.write(
            self.style.SUCCESS(f"Superusuario '{username}' creado correctamente.")
        )
