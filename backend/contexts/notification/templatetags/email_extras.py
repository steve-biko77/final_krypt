"""Tag de template dédié au restylage des emails (identité visuelle) — lit
``settings.FRONTEND_BASE_URL`` directement au rendu, sans dépendre du contexte
passé par l'appelant. Choix délibéré : DjangoEmailService (rendu via
``render_to_string`` sans ``request=``, donc sans context processors) et le
test ``test_email_template_renders_without_error`` (contexte minimal, pas de
frontend_base_url) doivent tous les deux continuer à fonctionner sans être
modifiés — ce tag évite d'avoir à toucher l'un ou l'autre pour référencer le
logo KRYPT (asset frontend, ``frontend/public/icons/logo.svg``) par une URL
absolue dans les emails.
"""
from django import template
from django.conf import settings

register = template.Library()


@register.simple_tag
def frontend_base_url():
    return settings.FRONTEND_BASE_URL
