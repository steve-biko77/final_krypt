"""Reçu PDF téléchargeable d'un transfert livré (page de suivi frontend).

Même approche que ``tracfin_report_generator.py`` (reportlab pur-Python,
aucune dépendance système supplémentaire) : styles/couleurs cohérents avec
l'identité visuelle de l'app (navy #00214F, bleu d'accent #1570EF, gris
#667085/#EAECF0 — mêmes valeurs que les templates email restylés et le
design system frontend). Pas de logo image embarqué : reportlab ne rend pas
le SVG nativement et ajouter une dépendance (svglib) uniquement pour ça
aurait été disproportionné — "KRYPT" est traité en wordmark stylé, comme
dans tracfin_report_generator.py.
"""
import io

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
_BLUE = colors.HexColor("#1570EF")
_GRAY = colors.HexColor("#667085")
_BORDER = colors.HexColor("#EAECF0")
_CARD_BG = colors.HexColor("#FCFCFD")

POLYGONSCAN_TX_BASE = "https://amoy.polygonscan.com/tx"


def _kv_table(rows: list) -> Table:
    table = Table(rows, colWidths=[6 * cm, 10 * cm])
    table.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("TEXTCOLOR", (0, 0), (0, -1), _GRAY),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica-Bold"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BACKGROUND", (0, 0), (-1, -1), _CARD_BG),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("LINEBELOW", (0, 0), (-1, -1), 0.3, _BORDER),
                ("BOX", (0, 0), (-1, -1), 0.5, _BORDER),
            ]
        )
    )
    return table


def generate_transfer_receipt_pdf(data: dict) -> bytes:
    """Construit le PDF en mémoire et retourne ses octets bruts. ``data``
    attend les clés : transaction_id, created_at (str déjà formatée),
    amount_eur, amount_xaf, beneficiary_name, beneficiary_country, status,
    escrow_tx_hash (optionnel, None si pas encore ancré on-chain)."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=2 * cm, bottomMargin=2 * cm, leftMargin=2 * cm, rightMargin=2 * cm,
        # Non compressé : permet de vérifier le contenu par sous-chaîne dans
        # les octets du PDF si besoin (même idiome que le rapport TRACFIN).
        pageCompression=0,
    )
    styles = getSampleStyleSheet()
    story = []

    header_style = ParagraphStyle(
        "Header", parent=styles["Title"], textColor=_NAVY, fontSize=22, spaceAfter=2,
    )
    story.append(Paragraph("KRYPT", header_style))
    subtitle_style = ParagraphStyle(
        "Subtitle", parent=styles["Normal"], textColor=_GRAY, fontSize=11,
    )
    story.append(Paragraph("Reçu de transfert", subtitle_style))
    story.append(Spacer(1, 20))

    story.append(_kv_table([
        ["Référence", data.get("transaction_id", "—")],
        ["Date", data.get("created_at", "—")],
        ["Statut", data.get("status", "—")],
    ]))
    story.append(Spacer(1, 14))

    story.append(_kv_table([
        ["Montant envoyé", f"{data.get('amount_eur', '—')} EUR"],
        ["Montant reçu", f"{data.get('amount_xaf', '—')} FCFA"],
        ["Bénéficiaire", data.get("beneficiary_name", "—")],
        ["Pays destinataire", data.get("beneficiary_country", "—")],
    ]))

    escrow_tx_hash = data.get("escrow_tx_hash")
    if escrow_tx_hash:
        story.append(Spacer(1, 14))
        story.append(_kv_table([
            ["Référence on-chain (Escrow)", escrow_tx_hash],
        ]))
        story.append(Spacer(1, 6))
        polygonscan_url = f"{POLYGONSCAN_TX_BASE}/{escrow_tx_hash}"
        link_style = ParagraphStyle(
            "Link", parent=styles["Normal"], textColor=_BLUE, fontSize=9, leading=13,
        )
        story.append(
            Paragraph(
                "Cette référence peut être vérifiée publiquement sur Polygonscan : "
                f'<link href="{polygonscan_url}">{polygonscan_url}</link>',
                link_style,
            )
        )

    story.append(Spacer(1, 28))
    footer_style = ParagraphStyle(
        "Footer", parent=styles["Normal"], textColor=_GRAY, fontSize=8,
    )
    story.append(
        Paragraph("KRYPT — transferts internationaux rapides et transparents.", footer_style)
    )

    doc.build(story)
    return buffer.getvalue()
