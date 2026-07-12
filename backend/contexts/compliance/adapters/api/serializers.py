from rest_framework import serializers

from ...domain.entities import DocumentType


class KYCSubmitSerializer(serializers.Serializer):
    document_type = serializers.ChoiceField(
        choices=[dt.value for dt in DocumentType]
    )
    file = serializers.FileField()


class KYCReviewSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(
        choices=["APPROVED", "COMPLEMENT_REQUESTED", "REJECTED"]
    )
    comment = serializers.CharField(required=False, allow_blank=True, default="")
