# commands/database/account.py
#
# Implement comands for managing accounts

from cleo import Command

from starling_server.cli.commands.account.account_add import AccountAdd
from starling_server.cli.commands.account.account_delete import AccountDelete
from starling_server.server.app import db


class AccountCommand(Command):
    """
    Manage Banks and associated accounts.

    account
    """

    commands = [AccountAdd(), AccountDelete()]

    def handle(self):

        accounts = db.select_accounts()

        for idx, account in enumerate(accounts):
            # TODO add account balances
            self.line(f"<info>[{idx}] {account.bank.name}: {account.name}</info>")

        if self.option("help"):
            return self.call("help", self._config.name)
