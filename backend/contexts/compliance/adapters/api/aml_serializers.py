from rest_framework import serializers


class AMLScoreRequestSerializer(serializers.Serializer):
    amount = serializers.FloatField(min_value=0.01)
    beneficiary_name = serializers.CharField(max_length=200)
    beneficiary_country = serializers.CharField(max_length=2)
    transfer_id = serializers.CharField(max_length=100, required=False, default="")
