from app.storage.interface import StorageBackend
from app.storage.local import LocalStorageBackend


storage_backend = LocalStorageBackend("./uploads")


def get_storage() -> StorageBackend:
    return storage_backend
