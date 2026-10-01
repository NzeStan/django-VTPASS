from rest_framework import serializers

from vtpass.api.serializers import MoneyField, PhoneField, PurchaseOptionsSerializer
from vtpass.api.views.base import PurchaseAPIView, VerifyAPIView, VTpassAPIView


class BankAccountSerializer(serializers.Serializer):
    bank_code = serializers.CharField(max_length=32, help_text="variation_code from banks/, e.g. gtb")
    account_number = serializers.RegexField(r"^\d{10}$", error_messages={"invalid": "Enter a 10-digit account number."})


class BankTransferSerializer(BankAccountSerializer, PurchaseOptionsSerializer):
    amount = MoneyField()
    phone = PhoneField()


class BankListView(VTpassAPIView):
    def get(self, request):
        return self.ok(self.vt.bank.banks())


class BankAccountVerifyView(VerifyAPIView):
    def post(self, request):
        data = self.validate(BankAccountSerializer)
        details = self.vt.bank.verify_account(data["bank_code"], data["account_number"])
        return self.ok({"account_name": self.vt.bank.account_name(details), **details}, "Account verified.")


class BankTransferView(PurchaseAPIView):
    """Transfers always re-verify the account server-side before money is sent."""

    def post(self, request):
        data = self.validate(BankTransferSerializer)
        txn = self.vt.bank.transfer(
            data["bank_code"], data["account_number"], data["amount"], data["phone"],
            **self.purchase_options(data),
        )
        return self.purchase_response(txn)
