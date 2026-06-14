from rest_framework import serializers


class SimulateTransferResponseSerializer(serializers.Serializer):
    amount_eur = serializers.DecimalField(max_digits=10, decimal_places=2)
    fees_eur = serializers.DecimalField(max_digits=10, decimal_places=2)
    fees_percentage = serializers.DecimalField(max_digits=5, decimal_places=3)
    net_eur = serializers.DecimalField(max_digits=10, decimal_places=2)
    exchange_rate = serializers.DecimalField(max_digits=12, decimal_places=3)
    amount_xaf = serializers.DecimalField(max_digits=14, decimal_places=2)
