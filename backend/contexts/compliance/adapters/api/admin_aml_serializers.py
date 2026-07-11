from rest_framework import serializers


class AMLDecisionSerializer(serializers.Serializer):
    """PATCH /api/admin/aml/{id}/decide — premier niveau (approve/reject/escalate).

    ``motif`` est optionnel ici : son caractère obligatoire pour REJECT est
    validé par DecideAMLReviewUseCase (AdminReasonRequiredError), pas ici — la
    même règle doit s'appliquer identiquement au second niveau (escalated
    decide), donc elle vit dans le use case partagé, pas dans deux serializers.
    """

    action = serializers.ChoiceField(choices=["approve", "reject", "escalate"])
    motif = serializers.CharField(required=False, allow_blank=True, default="")


class EscalatedDecisionSerializer(serializers.Serializer):
    """PATCH /api/admin/aml/escalated/{id}/decide — second niveau : SEULEMENT
    approve/reject, jamais de ré-escalade (Fig. 10 point 5)."""

    action = serializers.ChoiceField(choices=["approve", "reject"])
    motif = serializers.CharField(required=False, allow_blank=True, default="")
