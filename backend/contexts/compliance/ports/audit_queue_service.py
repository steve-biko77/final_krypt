from abc import ABC, abstractmethod


class AuditQueueServicePort(ABC):
    """
    Port pour la Couche 4 (audit a posteriori). Permet à `ScoreAMLUseCase`
    d'enfiler une transaction `AUTO_APPROVED` échantillonnée pour review humaine
    différée, sans importer de modèle Django dans le use case.
    """

    @abstractmethod
    def enqueue(
        self,
        sender_id: str,
        transfer_id: str,
        aml_result_id: str,
        tag_ml_score: float,
    ) -> None:
        """Ajoute une entrée à la file d'audit détectif (contrôle a posteriori)."""
