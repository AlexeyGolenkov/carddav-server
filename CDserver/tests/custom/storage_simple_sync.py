from CDserver.storage import BaseCollection, multifilesystem


class Collection(multifilesystem.Collection):
    sync = BaseCollection.sync


class Storage(multifilesystem.Storage):
    _collection_class = Collection
