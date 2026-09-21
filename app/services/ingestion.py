import asyncio
from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document as LCDocument
from app.services.embeddings import embed_texts
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.documents import DocumentChunks, Document
from sqlalchemy import delete

class DocumentProcessor:
    def __init__(self, file_path: str, db: AsyncSession,document:Document) -> None:
        self.file_path = Path("./uploads") / file_path
        self.db = db
        self.document = document

    async def extract_text_from_pdf(self) -> list[LCDocument]:

        loader = PyPDFLoader(file_path=self.file_path)
        pages = await loader.aload()

        return pages

    async def chunk_text(self, text: list[LCDocument]) -> list[LCDocument]:

        splitter = RecursiveCharacterTextSplitter(
            separators=["\n\n", "\n", ".", " "],
            chunk_size=500,
            chunk_overlap=25,
        )

        chunks = await asyncio.to_thread(splitter.split_documents, text)
        return chunks

    async def process_document(self):
        try:
            self.document.status = "processing"
            await self.db.commit()

            print("STATUS CHANGED TO PROCESSING")

            text = await self.extract_text_from_pdf()

            print("TEXT EXTRACTED")

            chunks = await self.chunk_text(text)

            print(f"CHUNKS CREATED: {len(chunks)}")

            embeddings = await asyncio.to_thread(embed_texts,
                [chunk.page_content for chunk in chunks]
            )

            print("EMBEDDINGS CREATED")

            await self.db.execute(
                delete(DocumentChunks).where(
                    DocumentChunks.document_id == self.document.id
                )
            )

            for index, (chunk, embedding) in enumerate(
                zip(chunks, embeddings)
            ):
                self.db.add(
                    DocumentChunks(
                        document_id=self.document.id,
                        chunk_index=index,
                        content=chunk.page_content,
                        embedding=embedding,
                        company_id=self.document.company_id,
                    )
                )

            self.document.status = "ready"

            await self.db.commit()

        except Exception as e:
            print(f"INGESTION FAILED for document {self.document.id}: {e!r}")
            await self.db.rollback()

            self.document.status = "failed"
            await self.db.commit()
