"""KRYP-26 — Provision an MTN MoMo sandbox API user + key.

One-off helper to bootstrap sandbox credentials. It:
  1. generates a UUIDv4 (becomes the new API user's id/username),
  2. POST /v1_0/apiuser        (creates the sandbox user),
  3. POST /v1_0/apiuser/{id}/apikey  (mints the API key),
then PRINTS the resulting ``MTN_API_USER`` / ``MTN_API_KEY`` lines for the user
to paste into their own ``.env`` manually. It never writes a file and never edits
``.env``. Requires ``MTN_SUBSCRIPTION_KEY`` to be set.

Usage:
    ./venv/Scripts/python.exe manage.py setup_mtn_sandbox_user
"""
import uuid

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Provision an MTN MoMo sandbox API user and key (prints .env lines)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--callback-host",
            default="krypt.example.com",
            help="providerCallbackHost sent to MTN (placeholder is fine in sandbox).",
        )

    def handle(self, *args, **options):
        subscription_key = getattr(settings, "MTN_SUBSCRIPTION_KEY", "")
        if not subscription_key:
            raise CommandError(
                "MTN_SUBSCRIPTION_KEY absent. Renseignez-le dans votre .env "
                "(clé d'abonnement du produit Remittance sur momodeveloper.mtn.com) "
                "puis relancez cette commande."
            )

        base_url = getattr(
            settings, "MTN_BASE_URL", "https://sandbox.momodeveloper.mtn.com"
        ).rstrip("/")
        callback_host = options["callback_host"]
        reference_id = str(uuid.uuid4())
        headers = {
            "X-Reference-Id": reference_id,
            "Ocp-Apim-Subscription-Key": subscription_key,
            "Content-Type": "application/json",
        }

        # 1. Create the API user.
        create = requests.post(
            f"{base_url}/v1_0/apiuser",
            json={"providerCallbackHost": callback_host},
            headers=headers,
            timeout=30,
        )
        if create.status_code != 201:
            raise CommandError(
                f"Échec création apiuser ({create.status_code}): {create.text}"
            )

        # 2. Mint the API key.
        key_resp = requests.post(
            f"{base_url}/v1_0/apiuser/{reference_id}/apikey",
            headers={"Ocp-Apim-Subscription-Key": subscription_key},
            timeout=30,
        )
        if key_resp.status_code not in (200, 201):
            raise CommandError(
                f"Échec création apikey ({key_resp.status_code}): {key_resp.text}"
            )
        api_key = key_resp.json()["apiKey"]

        self.stdout.write(self.style.SUCCESS(
            "\nUtilisateur sandbox MTN créé. Collez ces lignes dans votre .env :\n"
        ))
        self.stdout.write(f"MTN_API_USER={reference_id}")
        self.stdout.write(f"MTN_API_KEY={api_key}")
