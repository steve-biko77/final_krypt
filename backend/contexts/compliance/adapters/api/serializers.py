from rest_framework import serializers

from ...domain.entities import DocumentType, KYCStatus


class KYCSubmitSerializer(serializers.Serializer):
    document_type = serializers.ChoiceField(
        choices=[dt.value for dt in DocumentType]
    )
    file = serializers.FileField()


class KYCReviewSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=[KYCStatus.APPROVED.value, KYCStatus.REJECTED.value]
    )
