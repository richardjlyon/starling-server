# db/edgedb/database.py
#
# Defines an edgedb database manager
import uuid
from typing import List

import edgedb

from starling_server.db.db_base import DBBase
from starling_server.server.schemas.account import AccountSchema
from starling_server.server.schemas.transaction import TransactionSchema


class Database(DBBase):
    def __init__(self, database: str = None):
        super().__init__()
        self.client = edgedb.create_client(database=database)

    def reset(self, accounts: List[AccountSchema]):
        """Drop Bank and Account tables and reconfigure from a list of accounts."""

        print("RESET")
        self.client.query(
            """
            delete Bank;
            """
        )

        for account in accounts:
            print(account)

    # noinspection SqlNoDataSourceInspection
    def insert_or_update_account(self, bank_name: str, account: AccountSchema):

        # ensure Bank exists: note - this can probably be combined with the `insert Account` query
        self.client.query(
            """
            insert Bank {
                name := <str>$name
            } unless conflict
            """,
            name=bank_name,
        )
        account_db = self.client.query(
            """
            with bank := (
                select Bank filter .name = <str>$bank_name
            )
            insert Account {
                bank := bank,
                uuid := <uuid>$uuid,
                name := <str>$name,
                currency := <str>$currency,
                created_at := <datetime>$created_at
            } unless conflict on .uuid else (
                update Account 
                set {
                    name := <str>$name,
                    currency := <str>$currency,
                    created_at := <datetime>$created_at,
                }
            );
            """,
            bank_name=bank_name,
            uuid=account.uuid,
            name=account.account_name,
            currency=account.currency,
            created_at=account.created_at,
        )
        self.client.close()
        return account_db

    # noinspection SqlNoDataSourceInspection
    def get_accounts(self, as_schema: bool = False) -> List[AccountSchema]:
        accounts_db = self.client.query(
            """
            select Account {
                bank: { name },
                uuid,
                name,
                currency,
                created_at
            }
            """
        )
        if as_schema:
            return [
                AccountSchema(
                    uuid=str(account_db.uuid),
                    bank_name=account_db.bank.name,
                    account_name=account_db.name,
                    currency=account_db.currency,
                    created_at=account_db.created_at,
                )
                for account_db in accounts_db
            ]
        else:
            return accounts_db

    # noinspection SqlNoDataSourceInspection
    def insert_or_update_transaction(self, transaction: TransactionSchema):
        transaction_db = self.client.query(
            """
            with account := (
                select Account filter .uuid = <uuid>$account_uuid
            )
            insert Transaction {
                account := account,
                uuid := <uuid>$uuid,
                time := <datetime>$time,
                counterparty_name := <str>$counterparty_name,
                amount := <float32>$amount,
                reference := <str>$reference
            } unless conflict on .uuid else (
                update Transaction
                set {
                    time := <datetime>$time,
                    counterparty_name := <str>$counterparty_name,
                    amount := <float32>$amount,
                    reference := <str>$reference
                }
            )
            """,
            account_uuid=transaction.account_uuid,
            uuid=transaction.uuid,
            time=transaction.time,
            counterparty_name=transaction.counterparty_name,
            amount=transaction.amount,
            reference=transaction.reference,
        )
        self.client.close()
        return transaction_db

    # noinspection SqlNoDataSourceInspection
    def get_transactions_for_account(self, account_uuid: uuid.UUID):
        transactions = self.client.query(
            """
            select Account {
                transactions: {
                    uuid,
                    amount
                }
            }
            filter Account.uuid = <uuid>$account_uuid
            
            """,
            account_uuid=account_uuid,
        )
        self.client.close()
        return transactions

    # noinspection SqlNoDataSourceInspection
    def get_last_transaction_date_for_account(self, account_uuid: uuid.UUID):

        transaction = self.client.query(
            """
            with account := (
                select Account filter .uuid = <uuid>$account_uuid
            )
            select Transaction { time }
            filter account = account
            order by .time desc;

            """,
            account_uuid=account_uuid,
        )
        self.client.close()
        return transaction
