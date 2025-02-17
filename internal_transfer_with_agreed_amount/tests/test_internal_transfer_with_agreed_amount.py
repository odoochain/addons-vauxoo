from odoo.tests import Form, TransactionCase, tagged


@tagged("internal_transfer_multicurrency", "post_install", "-at_install")
class TestInternalTransferWithAgreedAmount(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.currency_usd = cls.env.ref("base.USD")
        cls.currency_eur = cls.env.ref("base.EUR")
        bank = cls.env["account.journal"].search([("type", "=", "bank")], limit=1)
        cls.bank_journal_usd = bank.copy()
        cls.bank_journal_usd.write({"name": "Bank US", "code": "BNK68"})
        cls.bank_journal_eur = bank.copy({"currency_id": cls.currency_eur.id})
        cls.bank_journal_eur.write({"name": "Bank EUR", "code": "BNK67"})
        account = cls.bank_journal_usd.default_account_id
        payment_method = (
            cls.bank_journal_usd.inbound_payment_method_line_ids
            | cls.bank_journal_usd.outbound_payment_method_line_ids
        )
        payment_method.payment_account_id = account

    def create_internal_transfer(self, currency, journal, destination_journal, amount):
        transfer = Form(self.env["account.payment"])
        transfer.payment_type = "outbound"
        transfer.is_internal_transfer = True
        transfer.journal_id = journal
        transfer.currency_id = currency
        transfer.destination_journal_id = destination_journal
        transfer.amount = amount
        return transfer.save()

    def create_multicurrency_transfer(self, payment, agreed_amount, currency):
        ctx = {"active_model": payment._name, "active_ids": payment.ids}
        wizard = Form(self.env["internal.transfer.multicurrency"].with_context(**ctx))
        wizard.agreed_amount = agreed_amount
        wizard = wizard.save()
        wizard.apply()
        return wizard

    def test_01_transfer_usd_eur(self):
        transfer = self.create_internal_transfer(self.currency_usd, self.bank_journal_usd, self.bank_journal_eur, 100)
        self.create_multicurrency_transfer(transfer, 120, self.currency_eur)

        # Check journal item in USD
        usd_aml = transfer.line_ids.filtered("reconciled")
        self.assertRecordValues(
            usd_aml,
            [
                {
                    "balance": 100.0,  # payment amount
                    "amount_currency": 120.0,
                    "currency_id": self.currency_eur.id,
                }
            ],
        )

        # Check journal item in EUR
        eur_aml = usd_aml.full_reconcile_id.reconciled_line_ids.filtered(lambda l: l != usd_aml)
        self.assertRecordValues(
            eur_aml,
            [
                {
                    "balance": -100.0,  # payment amount
                    "amount_currency": -120.0,  # Agreed amount
                    "currency_id": self.currency_eur.id,
                }
            ],
        )

    def test_02_transfer_eur_usd(self):
        transfer = self.create_internal_transfer(self.currency_eur, self.bank_journal_eur, self.bank_journal_usd, 100)
        self.create_multicurrency_transfer(transfer, 80, self.currency_usd)

        # Check journal item in USD
        usd_aml = transfer.line_ids.filtered("reconciled")
        self.assertRecordValues(
            usd_aml,
            [
                {
                    "balance": 80.0,  # Agreed amount
                    "amount_currency": 100.0,
                    "currency_id": self.currency_eur.id,
                }
            ],
        )

        # Check journal item in EUR
        eur_aml = usd_aml.full_reconcile_id.reconciled_line_ids.filtered(lambda l: l != usd_aml)
        self.assertRecordValues(
            eur_aml,
            [
                {
                    "balance": -80.0,  # Agreed amount
                    "amount_currency": -100.0,  # Payment amount
                    "currency_id": self.currency_eur.id,
                }
            ],
        )
