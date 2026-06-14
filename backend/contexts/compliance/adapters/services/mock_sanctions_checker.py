from difflib import SequenceMatcher

from ...ports.sanctions_check_service import SanctionsCheckServicePort, SanctionsResult

# Fictional sanctioned entities for testing purposes only
_SANCTIONED_NAMES = [
    "Viktor Petrov Rosneft",
    "Ahmad Khalil Al-Nusra",
    "Kim Jong Sanctions Corp",
    "Hassan Al-Irani Holdings",
    "Yevgeny Prigozhin Wagner Group",
]

_SIMILARITY_THRESHOLD = 0.85


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


class MockSanctionsChecker(SanctionsCheckServicePort):
    """
    Mock OFAC/EU sanctions checker using a hardcoded list of fictional names.
    A real integration with the OFAC SDN API will replace this in Sprint 3.

    Matching: Levenshtein-equivalent similarity > 0.85 → confirmed match (HARD_BLOCK).
    """

    def check(self, name: str, country: str) -> SanctionsResult:
        for sanctioned in _SANCTIONED_NAMES:
            ratio = _similarity(name, sanctioned)
            if ratio >= _SIMILARITY_THRESHOLD:
                return SanctionsResult(
                    is_match=True,
                    details={
                        "matched_entry": sanctioned,
                        "similarity": round(ratio, 4),
                        "list": "OFAC-SDN",
                        "beneficiary_name": name,
                        "beneficiary_country": country,
                    },
                    source="OFAC/EU",
                )

        return SanctionsResult(
            is_match=False,
            details={"checked_name": name, "checked_country": country},
            source="OFAC/EU",
        )
