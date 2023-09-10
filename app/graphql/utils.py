import typing
import strawberry

GenericType = typing.TypeVar("GenericType")


@strawberry.type
class PaginationWindow(typing.List[GenericType]):
    items: typing.List[GenericType] = strawberry.field(
        description="The list of items in the window."
    )
    count: int = strawberry.field(
        description="The total number of items in the list."
    )
