# tests/conftest.py
#
# provides general test fixtures and utilities
import json
import pathlib
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from random import random
from typing import List

import pytest
import pytz
from pydantic import parse_obj_as, PydanticTypeError

from starling_server import cfg
from starling_server.db.edgedb.database import Database
from starling_server.handlers.account import Account, get_provider_class, get_auth_token
from starling_server.mappers.name_mapper import NameMapper, NameDisplayname
from starling_server.providers.starling.schemas import (
    StarlingTransactionsSchema,
    StarlingTransactionSchema,
)
from starling_server.schemas import AccountSchema
from starling_server.schemas import (
    TransactionSchema,
)
from starling_server.schemas.transaction import Counterparty, Category, CategoryGroup
from .secrets import token_filepath

testdb = Database(database="test")

TEST_FOLDER = pathlib.Path(__file__).parent.absolute()

test_bank_name = "Starling Personal"

personal_account = {
    "bank_name": "Starling Personal",
    "account_uuid": "5b692051-b699-40f8-a48b-d14d554a9bd1",
    "default_category": "b23c9e8b-4377-4d9a-bce3-e7ee5477af50",
}

business_account = {
    "bank_name": "Starling Business",
    "account_uuid": "7327c655-31f6-4f21-ac8e-74880e5c8a47",
    "default_category": "8a489b6e-8d06-4e21-a122-e4e4ed3e2d84",
}


@dataclass
class Config:
    bank_name: str
    account_uuid: uuid.UUID
    token: str


@pytest.fixture()
def config():
    with open(token_filepath, "r") as f:
        token = f.read().strip()

    return Config(
        bank_name=personal_account["bank_name"],
        account_uuid=uuid.UUID(personal_account["account_uuid"]),
        token=token,
    )


# Database fixtures ==================================================================================================


@pytest.fixture
def empty_db():
    """Returns an empty test database, and destroys its contents after testing."""
    reset(testdb.client)
    yield testdb
    # reset() # FIXME allows the database to be inspected - uncomment this when done


@pytest.fixture
def db_2_accounts(empty_db, config):
    """Inserts two test accounts."""
    accounts = make_accounts(2)
    for account in accounts:
        empty_db.account_upsert(config.token, account)
    return empty_db


@pytest.fixture
@pytest.mark.asyncio
async def testdb_with_real_accounts(empty_db, config):
    """Returns a test database populated with accounts from the config file.

    This is necessary for tests that require a provider object to be created.
    """
    await initialise_accounts(empty_db)
    return empty_db


@pytest.fixture
def db_with_transactions(db_2_accounts):
    """Inserts 2 accounts of 8 transactions each."""
    accounts_db = select_accounts(db_2_accounts)
    for account_db in accounts_db:
        transactions = make_transactions(8, account_uuid=account_db.uuid)
        for transaction in transactions:
            db_2_accounts.transaction_upsert(transaction)

    return db_2_accounts


# RouteDispatcher fixtures ===========================================================================================


@pytest.fixture
def account():
    return Account(
        schema=AccountSchema(
            uuid=uuid.UUID("5b692051-b699-40f8-a48b-d14d554a9bd1"),
            bank_name="Starling Personal",
            account_name="Personal",
            currency="GBP",
            created_at=datetime(2018, 7, 7, 11, 32, 14, 888000, tzinfo=timezone.utc),
        )
    )


@pytest.fixture
def mock_transactions() -> List[TransactionSchema]:
    """Generate a list of transactions from a file to avoid an api call."""
    transaction_data_file = TEST_FOLDER / "test_data" / "transactions.json"
    with open(transaction_data_file, "r") as f:
        response = json.load(f)
    try:
        parsed_response = parse_obj_as(StarlingTransactionsSchema, response)
    except PydanticTypeError:
        raise RuntimeError(f"Pydantic type error")
    transactions_raw = parsed_response.feedItems
    account_uuid = uuid.uuid4()
    return [
        StarlingTransactionSchema.to_server_transaction_schema(
            account_uuid, transaction
        )
        for transaction in transactions_raw
    ]


# Transaction Processor fixtures ======================================================================================


@pytest.fixture(name="dmm_unpopulated")
def unpopulated_displaynamemap_manager(empty_db):
    """Returns an unpopulated displayname manager."""
    return NameMapper(empty_db)


@pytest.fixture(name="dmm_populated")
def populated_displaynamemap_manager(dmm_unpopulated):
    """Returns a displayname manager with sample entries."""
    dmm_unpopulated.insert(
        NameDisplayname(name="Waterstones", displayname="Waterstones")
    )
    dmm_unpopulated.insert(
        NameDisplayname(name="Acme coffee biz", displayname="Wee cafe at bus stop")
    )
    dmm_unpopulated.insert(NameDisplayname(name="BP", displayname="BP Petrol"))
    return dmm_unpopulated


# Route Dispatcher fixtures ===========================================================================================


@pytest.fixture()
def accounts(db_with_transactions):
    """Returns a list of accounts from the database"""
    return [
        Account(account_schema)
        for account_schema in testdb_with_real_accounts.select_accounts(as_schema=True)
    ]


# Helpers ==========================================================================================================


def reset(client):
    client.query(
        """
        delete Transaction;
        """
    )
    client.query(
        """
        delete Account;
        """
    )
    client.query(
        """
        delete Bank;
        """
    )
    client.query(
        """
        delete Category;
        """
    )
    client.query(
        """
        delete CategoryGroup;
        """
    )
    client.query(
        """
        delete Counterparty;
        """
    )
    client.query(
        """
        delete DisplaynameMap;
        """
    )
    client.query(
        """
        delete CategoryMap;
        """
    )
    client.close()


def insert_bank(db, name):
    db.client.query(
        """
        insert Bank {
            name := <str>$name,
        }
        """,
        name=name,
    )


def select_banks(db):
    banks = db.client.query(
        """
        select Bank { name }
        """
    )
    db.client.close()
    return banks


def make_accounts(n) -> List[AccountSchema]:
    """Make n test accounts."""
    return [
        AccountSchema(
            uuid=uuid.uuid4(),
            bank_name=f"Starling Personal {i}",
            account_name=f"Account {i}",
            currency="GBP",
            created_at=datetime.now(pytz.timezone("Europe/London")),
        )
        for i in range(n)
    ]


@pytest.mark.asyncio
async def initialise_accounts(empty_db) -> None:
    """Initialise the test database with a bank and account."""
    bank_names = [bank["bank_name"] for bank in cfg.banks]
    for bank_name in bank_names:
        provider_class = get_provider_class(bank_name)
        auth_token = get_auth_token(bank_name)
        provider = provider_class(
            auth_token=auth_token, bank_name=bank_name, category_check=False
        )
        accounts = await provider.get_accounts()
        for account in accounts:
            empty_db.account_upsert(provider.auth_token, account)

    return empty_db


def insert_account(db, name):
    account_uuid = uuid.uuid4()
    db.client.query(
        """
        with bank := (select Bank filter .name = <str>$bank_name)
        insert Account {
            bank := bank,
            uuid := <uuid>$uuid,
            name := <str>$name,
            currency := "GBP",
            created_at := <datetime>$now,
        }
        """,
        bank_name=test_bank_name,
        uuid=account_uuid,
        name=name,
        now=datetime.now(pytz.timezone("Europe/London")),
    )


def select_accounts(db):
    accounts = db.client.query(
        """
        select Account {
            bank: { name },
            uuid,
            name,
            currency,
            created_at,
            transactions: { reference }
        };
        """
    )
    db.client.close()
    return accounts


def make_transactions(number: int, account_uuid: uuid.UUID) -> List[TransactionSchema]:
    reference_date = datetime(2020, 1, 1, tzinfo=pytz.timezone("Europe/London"))
    dates = [reference_date + timedelta(hours=i) for i in range(number)]

    return [
        TransactionSchema(
            uuid=uuid.uuid4(),
            account_uuid=account_uuid,
            time=dates[i],
            counterparty=Counterparty(
                uuid=uuid.uuid4(),
                name=f"Counterparty {i}",
                display_name=f"Counterparty Display {i}",
            ),
            amount=random() * 10000,
            reference=f"{str(account_uuid)[-4:]}/{i}",
        )
        for i in range(number)
    ]


def insert_transaction(db, account_uuid):
    counterparty_uuid = uuid.uuid4()
    counterparty = Counterparty(uuid=counterparty_uuid, name="DUMMY")
    upsert_counterparty(db, counterparty)
    categories = make_categories()
    db.client.query(
        """
        with 
            account := (select Account filter .uuid = <uuid>$account_uuid),
            category := (select Category filter .uuid = <uuid>$category_uuid),
            counterparty := (select Counterparty filter .uuid = <uuid>$counterparty_uuid),
        insert Transaction {
            account := account,
            category := category,
            uuid := <uuid>$transaction_uuid,
            time := <datetime>$transaction_time,
            counterparty := counterparty,
            amount := <float32>$amount,
            reference := <str>$reference,
        }
        """,
        account_uuid=account_uuid,
        category_uuid=categories[0].uuid,
        counterparty_uuid=counterparty_uuid,
        transaction_uuid=uuid.uuid4(),
        transaction_time=datetime.now(pytz.timezone("Europe/London")),
        amount=random() * 100,
        reference=f"Ref: {str(account_uuid)[-4:]}",
    )


def select_transactions(db):
    transactions = db.client.query(
        """
        select Transaction {
            account: { uuid, name },
            uuid,
            time,
            counterparty: {
                uuid, name
            },
            amount,
            reference
        };
        """
    )
    db.client.close()
    return transactions


def select_displaynames(db):
    displaynames = db.client.query(
        """
        select DisplaynameMap {
            name,
            displayname
        };
        """
    )
    db.client.close()
    return displaynames


def select_categories(db):
    categories = db.client.query(
        """
        select Category {
            uuid,
            name,
            category_group: { name }
        };
        """
    )
    db.client.close()
    return categories


def make_categories() -> List[Category]:
    data = {
        "Mandatory": ["Energy", "Food", "Insurance"],
        "Discretionary": ["Entertainment", "Hobbies", "Vacation"],
    }
    category_list = []
    for group_name, categories in data.items():
        group = CategoryGroup(name=group_name)
        for category_name in categories:
            category = Category(
                name=category_name,
                group=group,
            )
            category_list.append(category)

    return category_list


def insert_categories(db) -> List[Category]:
    categories = make_categories()
    for category in categories:
        db.category_upsert(category)

    return categories


def upsert_counterparty(db, counterparty: Counterparty):
    db.client.query(
        """
        insert Counterparty {
            uuid := <uuid>$uuid,
            name := <str>$name,
        } unless conflict on .uuid else (
            update Counterparty
            set {
                name := <str>$name,
            }
        )
        """,
        uuid=counterparty.uuid,
        name=counterparty.name,
    )


def show(things: List, message=None) -> None:
    print()
    if message is not None:
        print(f"\n{message}\n===========================:")
    for thing in things:
        print(thing)
