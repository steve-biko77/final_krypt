from rest_framework import serializers


class AMLScoreRequestSerializer(serializers.Serializer):
    amount = serializers.FloatField(min_value=0.01)
    beneficiary_name = serializers.CharField(max_length=200)
    beneficiary_country = serializers.CharField(max_length=2)
    transfer_id = serializers.CharField(max_length=100, required=False, default="")
    # Optionnels : permettent d'exercer la RULE 3 (incohérence pays/opérateur)
    # depuis l'endpoint standalone sans casser les payloads existants qui les omettent.
    momo_number = serializers.CharField(max_length=30, required=False, default="", allow_blank=True)
    operator = serializers.CharField(max_length=20, required=False, default="", allow_blank=True)
