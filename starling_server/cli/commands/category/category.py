from typing import List

from cleo import Command

from starling_server.cli.commands.category.category_add import CategoryAdd
from starling_server.cli.commands.category.category_assign import CategoryAssign
from starling_server.cli.commands.category.category_change_group import (
    CategoryChangeGroup,
)
from starling_server.cli.commands.category.category_delete import CategoryDelete
from starling_server.cli.commands.category.category_init import CategoryInit
from starling_server.cli.commands.category.category_rename import CategoryRename
from starling_server.main import db
from starling_server.schemas.transaction import Category


class CategoryCommand(Command):
    """
    Manage adding, assigning, modifying, and removing categories.

    category
    """

    commands = [
        CategoryAdd(),
        CategoryDelete(),
        CategoryInit(),
        CategoryRename(),
        CategoryAssign(),
        CategoryChangeGroup(),
    ]

    def handle(self):

        categories = db.categories_select()
        self.show_category_table(categories)

        if categories is None:
            return

        if self.option("help"):
            return self.call("help", self._config.name)

    def show_category_table(self, categories: List[Category], sort: bool = True):
        if sort:
            categories.sort(key=lambda c: (c.group.name, c.name))
        table = self.table()
        table.set_header_row(["", "Category"])
        if categories:
            for idx, category in enumerate(categories):
                table.add_row([str(idx), f"{category.group.name}:{category.name}"])
            table.render(self.io)
