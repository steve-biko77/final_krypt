from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class SanctionsResult:
    is_match: bool
    details: dict = field(default_factory=dict)
    source: str = "OFAC/EU"


class SanctionsCheckServicePort(ABC):
    @abstractmethod
    def check(self, name: str, country: str) -> SanctionsResult:
        """Check a beneficiary against OFAC/EU sanctions lists."""
