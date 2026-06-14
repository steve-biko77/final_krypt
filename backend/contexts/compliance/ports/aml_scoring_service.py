from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class AMLScore:
    xgboost_score: float
    ofac_match: bool = False
    ofac_details: dict = field(default_factory=dict)


class AMLScoringServicePort(ABC):
    @abstractmethod
    def score(self, transaction_data: dict) -> AMLScore:
        """Score a transaction for AML risk using XGBoost model."""
