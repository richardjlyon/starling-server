"""
Module to handle the Starling API. Starling transactions are associated with a category ID which must be passed to the
API. Each transaction is assigned an account-specific default category ID which must be retrieved as part of
initialisation. A CategoryHelper class is provided to manage this process and provide the default category as
required
"""

import uuid
from datetime import datetime
from pathlib import Path
from typing import TypeVar, List

import httpx
import toml
from pydantic import PydanticTypeError, parse_obj_as

from starling_server import config_path
from starling_server.providers.provider import Provider
from starling_server.providers.starling.schemas import (
    StarlingAccountSchema,
    StarlingAccountsSchema,
    StarlingBalanceSchema,
    StarlingTransactionsSchema,
    StarlingTransactionSchema,
)
from starling_server.schemas import AccountSchema, AccountBalanceSchema
from starling_server.schemas import TransactionSchema

API_VERSION = "v2"
API_BASE_URL = f"https://api.starlingbank.com/api/{API_VERSION}"
CLASS_NAME = f"Starling_API_{API_VERSION}"

T = TypeVar("T")


class StarlingProvider(Provider):
    """Provides the API methods for a Starling Bank account."""

    default_category: uuid.UUID

    def __init__(
        self,
        auth_token: str,
        bank_name: str = None,
        account_uuid: uuid.UUID = None,
        category_check: bool = True,
    ):
        """
        Initialise an api account object.
        Args:
            auth_token (str): the bank's authorisation token for this account
            bank_name (str): name of the bank, used in AccountSchema
            account_uuid (str): uuid of the account
            category_check (bool): if False, bypass initialising the default category (i.e when getting it)
        """

        if account_uuid is not None and bank_name is None:
            raise ValueError("Missing bank_name for account_uuid")

        super().__init__(
            auth_token=auth_token,
            bank_name=bank_name,
            account_uuid=account_uuid,
            class_name=CLASS_NAME,
        )

        if category_check is True and account_uuid is not None:
            default_category = CategoryHelper()._category_for_account_id(account_uuid)
            if default_category is None:
                raise RuntimeError(
                    f"No default category for {bank_name} account {account_uuid} - check configuration"
                )
            self.default_category = default_category

    # = ABSTRACT METHOD IMPLEMENTATIONS ===============================================================================

    async def get_accounts(self) -> list[AccountSchema]:
        """
        Get all of the accounts associated with the authorisation token.

        Returns:
            A list of accounts
        """

        response = await self.get_accounts_raw()
        return self._to_account_schema_list(response)

    async def get_account_balance(self) -> AccountBalanceSchema:
        """Get the account balance associated with the account id."""
        path = f"/accounts/{self.account_uuid}/balance"
        response = await self._get_endpoint(path)
        return self._to_account_balance_schema(response)

    async def get_transactions_between(
        self, start_date: datetime, end_date: datetime
    ) -> List[TransactionSchema]:
        """Get the transactions for the account id between the given dates."""
        path = f"/feed/account/{self.account_uuid}/category/{self.default_category}/transactions-between"
        params = {
            "minTransactionTimestamp": start_date.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "maxTransactionTimestamp": end_date.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        }
        response = await self._get_endpoint(path, params)
        return self._to_transaction_schema_list(response)

    # = SCHEMA CONVERTORS =============================================================================================

    def _to_account_schema_list(self, response: dict) -> List[AccountSchema]:
        """Validate response and convert to a list of AccountSchema."""
        try:
            parsed_response = parse_obj_as(StarlingAccountsSchema, response)
        except PydanticTypeError:
            raise RuntimeError(f"Pydantic type error")  # FIXME add type

        accounts_raw = parsed_response.accounts
        accounts = [
            StarlingAccountSchema.to_server_account_schema(
                bank_name=self.bank_name, account=account
            )
            for account in accounts_raw
        ]

        return accounts

    def _to_account_balance_schema(self, response: dict) -> AccountBalanceSchema:
        """Validate response and convert to a AccountBalanceSchema."""
        try:
            parsed_response = parse_obj_as(StarlingBalanceSchema, response)
        except PydanticTypeError:
            raise RuntimeError(f"Pydantic type error")

        balance = parsed_response
        return StarlingBalanceSchema.to_server_account_balance_schema(
            self.account_uuid, balance
        )

    def _to_transaction_schema_list(self, response: dict) -> List[TransactionSchema]:
        """Validate response and convert to a list of TransactionSchema."""
        try:
            parsed_response = parse_obj_as(StarlingTransactionsSchema, response)
        except PydanticTypeError:
            raise RuntimeError(f"Pydantic type error")

        transactions_raw = parsed_response.feedItems
        transactions = [
            StarlingTransactionSchema.to_server_transaction_schema(
                self.account_uuid, transaction
            )
            for transaction in transactions_raw
        ]

        return transactions

    # = UTILITIES =====================================================================================================

    async def _get_endpoint(self, path: str, params: dict = None) -> dict:
        """Get an api endpoint."""

        headers = {
            "Authorization": f"Bearer {self.auth_token}",
            "User-Agent": "python",
        }
        url = f"{API_BASE_URL}{path}"

        async with httpx.AsyncClient() as client:
            try:
                r = await client.get(url, headers=headers, params=params)
                r.raise_for_status()
            except httpx.HTTPError as e:
                print(str(e))
                raise Exception(e)

            return r.json()

    async def get_accounts_raw(self) -> dict:
        """Get all of the accounts associated with the authorisation token as a raw json response."""
        path = "/accounts"
        return await self._get_endpoint(path)


class CategoryHelper:
    """A class to help manage Starling API default categories.

    Maintains a TOML file in the config folder with pairs of account uuid / default category uuid and provides CRUD
    methods to access them.
    """

    _storage_filepath: Path

    def __init__(self, storage_filepath: Path = None):
        # create the storage file if one isn't supplied or if the default doesn't exist
        if storage_filepath is None:
            storage_filepath = config_path.saveFolderPath() / "starling_config.yaml"
        if not storage_filepath.is_file():
            storage_filepath.touch()
        self._storage_filepath = storage_filepath

    async def insert(self, token: str, account_uuid: uuid.UUID, bank_name: str):
        """Add an account/category pair."""
        api = StarlingProvider(
            auth_token=token,
            account_uuid=account_uuid,
            bank_name=bank_name,
            category_check=False,
        )
        response = await api.get_accounts_raw()

        default_category = None
        # next() raises a StopIteration RuntimeError, so loop
        for account in response.get("accounts"):
            if account["accountUid"] == str(account_uuid):
                default_category = account["defaultCategory"]
                break

        if default_category is None:
            return

        config_file = self._load()
        config_file[str(account_uuid)] = default_category
        self._save(config_file)

    def remove(self, account_uuid: uuid.UUID):
        """Remove an account/category pair."""
        config_file = self._load()
        if str(account_uuid) in config_file:
            del config_file[str(account_uuid)]
            self._save(config_file)

    def _category_for_account_id(self, account_uuid: uuid.UUID) -> uuid.UUID:
        """Retrieve the category for the account id."""
        if account_uuid is not None:
            config_file = self._load()
            return uuid.UUID(config_file.get(str(account_uuid)))

    def _load(self):
        """Load the data from the file system."""
        with open(self._storage_filepath, "r") as f:
            return toml.load(f)

    def _save(self, config_file: dict):
        """Save the data to the file system."""
        with open(self._storage_filepath, "w") as f:
            toml.dump(config_file, f)
