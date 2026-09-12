from rest_framework import serializers


class InitiateTransferRequestSerializer(serializers.Serializer):
    beneficiary_name = serializers.CharField(max_length=200)
    beneficiary_country = serializers.CharField(max_length=2)
    momo_number = serializers.CharField(max_length=30)
    operator = serializers.ChoiceField(choices=["MTN_MOMO", "ORANGE_MONEY"])
    amount_eur = serializers.DecimalField(max_digits=10, decimal_places=2)


class SaveBeneficiaryRequestSerializer(serializers.Serializer):
    beneficiary_name = serializers.CharField(max_length=200)
    beneficiary_country = serializers.CharField(max_length=2)
    momo_number = serializers.CharField(max_length=30)
    operator = serializers.ChoiceField(choices=["MTN_MOMO", "ORANGE_MONEY"])


class SavedBeneficiaryResponseSerializer(serializers.Serializer):
    id = serializers.CharField()
    beneficiary_name = serializers.CharField()
    beneficiary_country = serializers.CharField()
    momo_number = serializers.CharField()
    operator = serializers.CharField()
    created_at = serializers.DateTimeField()
    last_used_at = serializers.DateTimeField(allow_null=True)


class SimulateTransferResponseSerializer(serializers.Serializer):
    amount_eur = serializers.DecimalField(max_digits=10, decimal_places=2)
    fees_eur = serializers.DecimalField(max_digits=10, decimal_places=2)
    fees_percentage = serializers.DecimalField(max_digits=5, decimal_places=3)
    net_eur = serializers.DecimalField(max_digits=10, decimal_places=2)
    exchange_rate = serializers.DecimalField(max_digits=12, decimal_places=3)
    amount_xaf = serializers.DecimalField(max_digits=14, decimal_places=2)
