from abc import ABC, abstractmethod
from dataclasses import dataclass

from ..domain.entities import KYCDocument


@dataclass
class AnalysisResult:
    score: float
    details: dict


class KYCAnalyzerServicePort(ABC):
    @abstractmethod
    def analyze(self, doc: KYCDocument) -> AnalysisResult:
        ...
