import logging
from dataclasses import asdict
from typing import Generic, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class SimpleDb(Generic[T]):
    """
    use as follows:
    jobdb = SimpleDb[JobItem]()
    and it will have linting.

    T needs to have .id functions (like JobItem and Mediaitem, ...):

    @dataclass
    class Item:
        id: uuid.UUID = field(default_factory=uuid.uuid4)


    """

    def __init__(self):
        # init the arguments
        pass

        # declare private props
        self._db: list[T] = []

    def add_item(self, item: T):
        self._db.insert(0, item)  # insert at first position (prepend)

    def get_recent_item(self) -> T:
        try:
            return self._db[0]
        except IndexError as exc:
            raise FileNotFoundError("database is empty") from exc

    def update_item(self, updated_item: T) -> T:
        # there is no routine, because we pass around the references to elements in db, its updated automatically...
        # see tests
        pass

    def del_item(self, item: T):
        self._db.remove(item)

    def clear(self):
        self._db.clear()

    def get_list_as_dict(self) -> list[T]:
        return [asdict(item) for item in self._db]

    def db_get_list(self) -> list[T]:
        return [item for item in self._db]

    def get_item_by_id(self, id: str) -> T:
        if not isinstance(id, str):
            raise RuntimeError("id is wrong type")

        # https://stackoverflow.com/a/7125547
        item = next((x for x in self._db if str(x.id) == id), None)  # fix: id could be uuid, force str here.

        if item is None:
            logger.error(f"item {id} not found!")
            raise FileNotFoundError(f"item {id} not found!")

        return item

    @property
    def length(self) -> int:
        return len(self._db)
