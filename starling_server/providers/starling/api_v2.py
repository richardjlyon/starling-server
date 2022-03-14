from typing import TypeVar

import httpx
from pydantic import PydanticTypeError, parse_obj_as

from starling_server.providers.api_base import BaseAPIV2
from starling_server.providers.starling.schemas import (
    StarlingAccountsSchema,
    StarlingAccountSchema,
)
from starling_server.server.schemas.account import AccountSchema

API_BASE_URL = "https://api.starlingbank.com/api/v2"
T = TypeVar("T")


def response(response_model):
    """Decorator to convert to response_model."""

    def decorated(func):
        async def wrapper(*args, **kwargs):
            try:
                response = await func(*args, **kwargs)
                parsed_response = parse_obj_as(response_model, response)
                accounts = parsed_response.accounts
                accounts = [
                    StarlingAccountSchema.to_server_accountschema(account)
                    for account in accounts
                ]
                return accounts
            except PydanticTypeError:
                raise RuntimeError(f"Pydantic type error for ")  # FIXME add type

        return wrapper

    return decorated


class APIV2(BaseAPIV2):
    def __init__(self, bank_name: str, auth_token: str):
        super().__init__(bank_name=bank_name, auth_token=auth_token)

    @response(response_model=StarlingAccountsSchema)
    async def get_accounts(self) -> list[AccountSchema]:
        """Get the accounts held at the bank."""
        path = "/accounts"
        return await _get(self.token, path, None)


# = UTILITIES ======================================================================================================


async def _get(token: str, path: str, params: dict = None) -> T:
    """Get an api call."""

    headers = {
        "Authorization": f"Bearer {token}",
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
