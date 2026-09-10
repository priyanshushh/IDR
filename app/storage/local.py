from pathlib import Path

import aiofiles
from fastapi import UploadFile

from app.storage.interface import StorageBackend


class LocalStorageBackend(StorageBackend):

    def __init__(self, base_dir: str = "./uploads"):
        self.base_dir = Path(base_dir)

    def _get_path(
        self,
        company_id,
        document_id,
        filename: str,
    ) -> Path:
        safe_filename = Path(filename).name

        return (
            self.base_dir
            / str(company_id)
            / str(document_id)
            / safe_filename
        )

    async def save(
        self,
        company_id,
        document_id,
        filename: str,
        file: UploadFile,
    ) -> str:

        path = self._get_path(
            company_id=company_id,
            document_id=document_id,
            filename=filename,
        )

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        async with aiofiles.open(path, "wb") as output:
            while chunk := await file.read(1024 * 1024):
                await output.write(chunk)

        return str(path.relative_to(self.base_dir))

    async def read(self, storage_key: str) -> bytes:
        path = self.base_dir / storage_key

        async with aiofiles.open(path, "rb") as file:
            return await file.read()

    async def delete(self, storage_key: str) -> None:
        path = self.base_dir / storage_key

        if path.exists():
            path.unlink()