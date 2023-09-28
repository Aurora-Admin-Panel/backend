from typing import List, TypeVar, Dict, Any, Generic
import strawberry

Item = TypeVar("Item")


@strawberry.type
class PaginationWindow(Generic[Item]):
    items: List[Item] = strawberry.field(
        description="The list of items in the window."
    )
    count: int = strawberry.field(
        description="The total number of items in the list."
    )
