import logging
from typing import Generic, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class SimpleDb(Generic[T]):
    """
    use as follows:
    jobdb = SimpleDb[JobItem]()
    and it will have linting.

    T needs to have .id and .asdict() functions (like JobItem and Mediaitem, ...):

    @dataclass
    class Item:
        id: uuid.UUID = field(default_factory=uuid.uuid4)

        def asdict(self) -> dict:
            out = {
                prop: getattr(self, prop)
                for prop in dir(self)
                if (
                    not prop.startswith("_")  # no privates
                    and not callable(getattr(__class__, prop, None))  # no callables
                    and not isinstance(getattr(self, prop), Path)  # no path instances (not json.serializable)
                )
            }
            return out

    """

    def __init__(self):
        # init the arguments
        pass

        # declare private props
        self._db: list[T] = []

    def add_item(self, item: T):
        self._db.insert(0, item)  # insert at first position (prepend)

    def get_recent_item(self) -> T:
        return self._db[0]

    def update_item(self, updated_item: T) -> T:
        for idx, item in enumerate(self._db):
            if updated_item == item:
                self._db[idx] = updated_item

        return self._db[idx]

    def del_item(self, item: T):
        self._db.remove(item)

    def clear(self):
        self._db.clear()

    def get_list_as_dict(self) -> list[T]:
        return [item.asdict() for item in self._db]

    def db_get_list(self) -> list[T]:
        return [item for item in self._db]

    def get_item_by_id(self, id: str) -> T:
        if not isinstance(id, str):
            raise RuntimeError("id is wrong type")

        # https://stackoverflow.com/a/7125547
        item = next((x for x in self._db if x.id == id), None)

        if item is None:
            logger.error(f"image {id} not found!")
            raise FileNotFoundError(f"image {id} not found!")

        return item

    @property
    def length(self) -> int:
        return len(self._db)
