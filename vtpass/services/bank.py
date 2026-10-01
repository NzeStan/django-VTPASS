"""Bank transfers to any Nigerian bank account (``bank-deposit``)."""

from vtpass.constants import ServiceID
from vtpass.exceptions import VTpassValidationError
from vtpass.services.airtime import ProductService
from vtpass.utils import first_present


class BankTransferService(ProductService):
    def banks(self):
        """Supported banks. Each ``variation_code`` (e.g. ``gtb``) is the bank code for the other calls."""
        return self.engine.get_variations(ServiceID.BANK_DEPOSIT)

    def verify_account(self, bank_code, account_number):
        """
        Resolve the account name before sending money. Returns VTpass' content,
        e.g. ``{"account_name": "TESTIMETRY ADAMS"}``. Always show this name to
        the customer for confirmation: transfers cannot be recalled.
        """
        self._check_account(account_number)
        return self.engine.verify(ServiceID.BANK_DEPOSIT, account_number, type=bank_code)

    @staticmethod
    def account_name(details):
        return first_present(details, "account_name", "accountName", "Customer_Name")

    def transfer(self, bank_code, account_number, amount, phone, verify=True, **options):
        """
        Send ``amount`` naira to ``account_number`` at ``bank_code``.

        With ``verify=True`` (default) the account is resolved first and the
        purchase is refused if VTpass cannot find it; the resolved name is
        stored in ``transaction.metadata["account_name"]``.
        """
        self._check_account(account_number)
        metadata = dict(options.pop("metadata", None) or {})
        if verify:
            name = self.account_name(self.verify_account(bank_code, account_number))
            if not name:
                raise VTpassValidationError("The account could not be verified.",
                                            errors={"account_number": ["Not found."]})
            metadata["account_name"] = name
        return self.engine.purchase(
            service_id=ServiceID.BANK_DEPOSIT,
            phone=phone,
            billers_code=account_number,
            variation_code=bank_code,
            lookup_variation=False,  # the bank code is not a priced plan; the amount is what is sent
            amount=amount,
            metadata=metadata,
            **options,
        )

    @staticmethod
    def _check_account(account_number):
        if not (str(account_number).isdigit() and len(str(account_number)) == 10):
            raise VTpassValidationError("Account numbers are 10 digits (NUBAN).",
                                        errors={"account_number": ["Invalid account number."]})
