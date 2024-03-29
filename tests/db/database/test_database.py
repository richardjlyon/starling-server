"""
These tests verify the functionality of the EdgeDB Class. They require database "test" in the edgedb instance.
"""

from starling_server.schemas import AccountSchema
from starling_server.schemas import TransactionSchema
from starling_server.schemas.transaction import Counterparty
from tests.conftest import (
    make_accounts,
    make_transactions,
    insert_categories,
    select_accounts,
    select_transactions,
    select_banks,
    select_categories,
)


class TestBank:
    def test_insert_bank(self, empty_db):
        # GIVEN an empty database
        # WHEN I insert a bank
        empty_db.bank_upsert(bank_name="Starling Personal (TEST)")

        # THEN the bank is inserted
        bank_db = empty_db.client.query("select Bank {name}")
        assert len(bank_db) == 1
        assert bank_db[0].name == "Starling Personal (TEST)"

    def test_delete_bank(self, db_2_accounts):
        # GIVEN a database with 2 banks with 2 accounts each
        banks = select_banks(db_2_accounts)
        accounts = select_accounts(db_2_accounts)
        assert len(banks) == 2
        assert len(accounts) == 2

        # WHEN I delete a bank
        bank_name = banks[0].name
        db_2_accounts.bank_delete(bank_name)

        # THEN the bank and its accounts and transactions are deleted
        banks = select_banks(db_2_accounts)
        accounts = select_accounts(db_2_accounts)
        assert len(banks) == 1
        assert len(accounts) == 1


class TestCategory:
    def test_insert_categories(self, empty_db):
        # GIVEN an empty database
        # WHEN I add categories
        insert_categories(empty_db)
        # THEN the categories are added
        assert len(empty_db.client.query("select CategoryGroup")) == 2
        assert len(empty_db.client.query("Select Category")) == 6
        categories = empty_db.client.query(
            "Select Category {name, category_group: { name }}"
        )
        assert categories[0].category_group.name == "Mandatory"

    def test_update_category_name(self, empty_db):
        # GIVEN a database with test categories
        categories = insert_categories(empty_db)
        # WHEN I update a category name
        category = categories[0]
        new_name = category.name + " (TEST)"
        category.name = new_name
        empty_db.category_upsert(category)
        # THEN the category is updated
        categories = select_categories(empty_db)
        assert new_name in [c.name for c in categories]

    def test_delete_category(self, empty_db):
        # GIVEN a database with test categories
        categories = insert_categories(empty_db)
        # WHEN I delete a category
        category = categories[0]
        empty_db.category_delete(category)
        # THEN the category is deleted
        categories = select_categories(empty_db)
        assert category.uuid not in [c.uuid for c in categories]


class TestAccount:
    # @pytest.mark.skip()
    def test_upsert_account_insert_2(self, empty_db, config):
        # GIVEN an empty database
        # WHEN I add two accounts
        accounts = make_accounts(2)
        for account in accounts:
            empty_db.account_upsert(config.token, account)

        # THEN two accounts are added
        accounts_db = select_accounts(empty_db)
        assert len(accounts_db) == 2
        # AND they are linked to the bank
        assert accounts_db[0].bank.name == accounts[0].bank_name

    def test_upsert_account_update_1(self, db_2_accounts, config):
        # GIVEN a database with two accounts

        # WHEN an account name is modified
        a = select_accounts(db_2_accounts)[0]
        modified_uuid = a.uuid
        modified_name = a.name + " **MODIFIED**"
        account = AccountSchema(
            uuid=a.uuid,
            bank_name=a.bank.name,
            account_name=modified_name,
            currency=a.currency,
            created_at=a.created_at,
        )
        db_2_accounts.account_upsert(config.token, account)

        # THEN the account name is updated
        accounts_db = select_accounts(db_2_accounts)
        account = next(
            account for account in accounts_db if account.uuid == modified_uuid
        )
        assert len(accounts_db) == 2
        assert account.name == modified_name

    def test_select_accounts(self, db_2_accounts):
        # GIVEN a database with 2 accounts
        # WHEN I select the accounts
        accounts = db_2_accounts.accounts_select()
        # THEN I get 2 accounts
        assert len(accounts) == 2

        pass

    def test_select_account_for_account_uuid(self, db_2_accounts):
        # GIVEN a database with 2 accounts
        # WHEN I select an account
        accounts = select_accounts(db_2_accounts)
        account_0_uuid = accounts[0].uuid
        account = db_2_accounts.account_select_for_uuid(account_uuid=account_0_uuid)

        # THEN I get the account
        assert account.uuid == account_0_uuid

    def test_delete_account_with_transactions(self, db_with_transactions):
        # GIVEN a database with 2 accounts with 2 transactions each
        accounts = select_accounts(db_with_transactions)
        transactions = select_transactions(db_with_transactions)
        assert len(accounts) == 2
        assert len(transactions) == 16

        # WHEN I delete a selected account
        accounts = select_accounts(db_with_transactions)
        account_0_uuid = accounts[0].uuid
        db_with_transactions.account_delete(account_uuid=account_0_uuid)

        # THEN that account and its transactions (only) are deleted
        accounts = select_accounts(db_with_transactions)
        transactions = select_transactions(db_with_transactions)
        assert len(accounts) == 1
        assert len(transactions) == 8


class TestTransaction:
    def test_insert_or_update_transaction_insert_2(self, db_2_accounts):
        # GIVEN a database with two accounts and no transactions
        # WHEN I insert transactions in each account
        transactions_db = select_transactions(db_2_accounts)
        assert len(transactions_db) == 0
        for account_db in select_accounts(db_2_accounts):
            transactions = make_transactions(2, account_uuid=account_db.uuid)
            for transaction in transactions:
                db_2_accounts.transaction_upsert(transaction)

        # THEN the transactions are inserted
        transactions_db = select_transactions(db_2_accounts)
        assert len(transactions_db) == 4

        # AND are in the right accounts
        for account_db in select_accounts(db_2_accounts):
            assert len(account_db.transactions) == 2
            account_uuid = str(account_db.uuid)
            for transaction_db in account_db.transactions:
                reference = transaction_db.reference
                assert account_uuid[-4:] == reference[0:4]  # see `make_transactions()`

    def test_insert_or_update_transaction_update_1(self, db_with_transactions):
        # GIVEN a database with 2 accounts of 2 transactions each
        # WHEN I update a transaction
        t = select_transactions(db_with_transactions)[0]
        modified_uuid = t.uuid
        modified_reference = t.reference + " **MODIFIED**"
        transaction = TransactionSchema(
            account_uuid=t.account.uuid,
            uuid=t.uuid,
            time=t.time,
            counterparty=Counterparty(
                uuid=t.counterparty.uuid,
                name=t.counterparty.name,
            ),  # FIXME get counterparty uuid
            amount=t.amount,
            reference=modified_reference,
        )
        db_with_transactions.transaction_upsert(transaction)

        # THEN transaction is updated
        transactions = select_transactions(db_with_transactions)
        transaction = next(t for t in transactions if t.uuid == modified_uuid)
        assert "**MODIFIED**" in transaction.reference

    def test_select_transactions_for_account(self, db_with_transactions):

        # GIVEN a database with 2 accounts of 8 transactions each
        # WHEN I select the transactions for the personal account
        accounts = select_accounts(db_with_transactions)
        transactions = db_with_transactions.transactions_select_for_account_uuid(
            accounts[0].uuid
        )

        # THEN I get the transactions
        assert len(transactions) == 8

    def test_select_transactions_returns_none(self, db_2_accounts):
        accounts = select_accounts(db_2_accounts)
        transactions = db_2_accounts.transactions_select_for_account_uuid(
            accounts[0].uuid
        )
        assert transactions is None

    def test_delete_transactions_for_account_id(self, db_with_transactions):
        # GIVEN a database with transactions
        # WHEN I delete all transactions for a selected account
        accounts = select_accounts(db_with_transactions)
        account_uuid = accounts[0].uuid
        db_with_transactions.transactions_delete_for_account_uuid(account_uuid)

        # THEN all transactions for that account (only) are deleted
        accounts = select_accounts(db_with_transactions)
        assert len(accounts[0].transactions) == 0
        assert len(accounts[1].transactions) > 0


class TestDeleteMethods:
    # @pytest.mark.skip(reason="Not implemented")
    def test_reset(self, db_with_transactions):
        # GIVEN a database with banks, accounts, and transactions
        # WHEN I invoke reset()
        db_with_transactions.reset()

        # THEN All banks, accounts, and transactions are deleted
        assert len(select_banks(db_with_transactions)) == 0
        assert len(select_accounts(db_with_transactions)) == 0
        assert len(select_transactions(db_with_transactions)) == 0
