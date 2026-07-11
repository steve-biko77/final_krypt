"""KRYP-31 (partie 2/3) — Génération d'un PDF de déclaration de soupçon
structurellement représentatif d'une déclaration TRACFIN française (image 2,
section 4 : "generate TRACFIN declaration report").

AVERTISSEMENT — ce document N'A AUCUNE VALEUR LÉGALE : c'est un projet
étudiant, jamais transmis à TRACFIN. Le PDF généré porte cette mention de
façon visible (voir ``_disclaimer`` ci-dessous), conformément à la consigne du
ticket ("mention claire... document généré dans le cadre d'un projet
académique, pas d'une déclaration officiellement transmise").

Rubriques reprises (structure réelle d'une déclaration de soupçon) :
  1. Identité du déclarant (établissement assujetti)
  2. Identité complète de la personne concernée (émetteur du transfert)
  3. Caractéristiques de l'opération (montant, date, bénéficiaire, pays)
  4. Élément(s) ayant motivé le soupçon (résultat du contrôle OFAC/EU)
  5. Pièces justificatives disponibles

``reportlab`` : bibliothèque PDF pure-Python déjà choisie car elle ne demande
aucune dépendance système (contrairement à weasyprint/wkhtmltopdf), cohérente
avec le reste de la stack Python de ce backend.
"""
import io
from datetime import datetime, timezone

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

_NAVY = colors.HexColor("#00214F")
_GRAY = colors.HexColor("#667085")


def _section_title(text: str, styles) -> Paragraph:
    style = ParagraphStyle(
        "SectionTitle", parent=styles["Heading2"], textColor=_NAVY, spaceBefore=14, spaceAfter=6,
    )
    return Paragraph(text, style)


def _kv_table(rows: list) -> Table:
    table = Table(rows, colWidths=[6 * cm, 10 * cm])
    table.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TEXTCOLOR", (0, 0), (0, -1), _GRAY),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#EAECF0")),
            ]
        )
    )
    return table


def generate_tracfin_report_pdf(data: dict) -> bytes:
    """Construit le PDF en mémoire et retourne ses octets bruts (prêts pour
    ``StorageService.upload_file``). ``data`` attend les clés :
    transaction_id, generated_at, admin_email, sender_name, sender_email,
    sender_phone, sender_kyc_verified, amount_eur, amount_xaf,
    beneficiary_name, beneficiary_country, transfer_created_at,
    ofac_matched_entry, ofac_similarity, ofac_list, triggered_rules."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=2 * cm, bottomMargin=2 * cm, leftMargin=2 * cm, rightMargin=2 * cm,
        # Non compressé : permet de vérifier la mention académique par simple
        # recherche de sous-chaîne dans les octets du PDF (tests), sans
        # dépendance supplémentaire d'extraction PDF. Taille de fichier
        # négligeable pour un document de cette taille.
        pageCompression=0,
    )
    styles = getSampleStyleSheet()
    story = []

    title_style = ParagraphStyle(
        "Title", parent=styles["Title"], textColor=_NAVY, fontSize=16,
    )
    story.append(Paragraph("Déclaration de soupçon — Projet KRYPT", title_style))

    disclaimer_style = ParagraphStyle(
        "Disclaimer", parent=styles["Normal"], textColor=colors.HexColor("#B42318"),
        backColor=colors.HexColor("#FEF3F2"), borderPadding=8, fontSize=9, leading=13,
    )
    story.append(Spacer(1, 8))
    story.append(
        Paragraph(
            "<b>AVERTISSEMENT — DOCUMENT ACADÉMIQUE SANS VALEUR LÉGALE.</b> "
            "Ce document est généré dans le cadre d'un projet étudiant (KRYPT). "
            "Il reproduit la structure d'une déclaration de soupçon TRACFIN à "
            "titre de démonstration UNIQUEMENT. Il n'a JAMAIS été transmis à "
            "TRACFIN ni à aucune autorité réelle et n'a AUCUNE VALEUR LÉGALE.",
            disclaimer_style,
        )
    )
    story.append(Spacer(1, 12))

    generated_at = data.get("generated_at") or datetime.now(timezone.utc)
    story.append(
        Paragraph(
            f"Référence dossier interne : {data['transaction_id']} — "
            f"Généré le {generated_at.strftime('%d/%m/%Y à %H:%M UTC')}",
            styles["Normal"],
        )
    )

    # 1. Identité du déclarant.
    story.append(_section_title("1. Identité du déclarant", styles))
    story.append(_kv_table([
        ["Établissement assujetti", "KRYPT SAS (fictif — projet académique)"],
        ["Déclarant (admin)", data.get("admin_email", "—")],
    ]))

    # 2. Identité de la personne concernée (émetteur).
    story.append(_section_title("2. Identité de la personne concernée", styles))
    story.append(_kv_table([
        ["Nom", data.get("sender_name", "—")],
        ["Email", data.get("sender_email", "—")],
        ["Téléphone", data.get("sender_phone", "—")],
        ["Identité vérifiée (KYC)", "Oui" if data.get("sender_kyc_verified") else "Non"],
    ]))

    # 3. Caractéristiques de l'opération.
    story.append(_section_title("3. Caractéristiques de l'opération", styles))
    story.append(_kv_table([
        ["Montant envoyé", f"{data.get('amount_eur', '—')} EUR"],
        ["Montant destinataire", f"{data.get('amount_xaf', '—')} FCFA"],
        ["Bénéficiaire", data.get("beneficiary_name", "—")],
        ["Pays destinataire", data.get("beneficiary_country", "—")],
        ["Date de l'opération", data.get("transfer_created_at", "—")],
    ]))

    # 4. Élément(s) ayant motivé le soupçon.
    story.append(_section_title("4. Élément(s) ayant motivé le soupçon", styles))
    story.append(_kv_table([
        ["Liste de sanctions", data.get("ofac_list", "OFAC/EU")],
        ["Entrée correspondante", data.get("ofac_matched_entry", "—")],
        ["Score de similarité", f"{data.get('ofac_similarity', '—')}"],
        ["Règles métier déclenchées", ", ".join(data.get("triggered_rules") or []) or "—"],
    ]))

    # 5. Pièces justificatives disponibles.
    story.append(_section_title("5. Pièces justificatives disponibles", styles))
    story.append(
        Paragraph(
            f"Dossier de conformité interne KRYPT (transaction {data['transaction_id']}) : "
            "résultat de scoring AML horodaté, journal d'audit des décisions "
            "admin, trace on-chain (AuditTrail) des événements critiques liés "
            "à ce dossier.",
            styles["Normal"],
        )
    )

    doc.build(story)
    return buffer.getvalue()
