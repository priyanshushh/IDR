from abc import ABC, abstractmethod

from fastapi import UploadFile


class StorageBackend(ABC):

    @abstractmethod
    async def save(
        self,
        company_id: str,
        document_id: str,
        filename: str,
        file: UploadFile,
    ) -> str:
        pass

    @abstractmethod
    async def read(self, storage_key: str) -> bytes:
        pass

    @abstractmethod
    async def delete(self, storage_key: str) -> None:
        pass
