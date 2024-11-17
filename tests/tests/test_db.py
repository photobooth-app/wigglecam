"""
Testing virtual camera Backend
"""

import logging

from wigglecam.services.dto import JobItem
from wigglecam.utils.simpledb import SimpleDb

logger = logging.getLogger(name=None)


def test_database_items():
    item1 = JobItem(request=None)
    item2 = JobItem(request=None, id=item1.id)

    # means it's not same instance
    assert item1 is not item2
    # but is same because Id was passed which is unique by default init
    assert item1 == item2


def test_database_get_is_ref():
    item1 = JobItem(request=None)

    db = SimpleDb[JobItem]()

    db.add_item(item1)

    item1_ = db.get_recent_item()

    assert item1 is item1_


def test_database_updated_by_ref():
    item1 = JobItem(request=None)

    db = SimpleDb[JobItem]()

    db.add_item(item1)

    item1_ = db.get_recent_item()

    # update the ref
    item1_.id = "22"

    assert item1 is item1_
    assert item1.id == "22"
    assert item1_.id == "22"

    item1__ = db.get_item_by_id("22")
    assert item1__ is item1
