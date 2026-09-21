import asyncio
from pathlib import Path

from unstructured.partition.auto import partition
from unstructured.chunking.title import chunk_by_title
from unstructured.documents.elements import Element

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

    async def extract_elements(self) -> list[Element]:
        # partition()'s filename arg has to be a plain str — python-magic's ctypes
        # binding (used internally for file-type detection) can't marshal a Path
        # object and raises deep inside: `ctypes.ArgumentError: argument 2: TypeError:
        # wrong type`.
        #
        # strategy="hi_res" runs the layout detection model instead of just pulling
        # raw text, and skip_infer_table_types=[] makes it actually recognize Table
        # elements (default strategy is "auto", which falls back to "fast" for
        # text-based PDFs and never detects tables at all).
        return await asyncio.to_thread(
            partition,
            filename=str(self.file_path),
            strategy="hi_res",
            skip_infer_table_types=[],
        )


    async def chunk_elements(self,elements: list[Element])->list:
        return await asyncio.to_thread(
            chunk_by_title,
            elements,
            max_characters=800,
            combine_text_under_n_chars=200,
            new_after_n_chars=700,
        )
        
    

    async def process_document(self):
        try:
            self.document.status = "processing"
            await self.db.commit()

            print("STATUS CHANGED TO PROCESSING")

            elements = await self.extract_elements()
            
            print("ELEMENTS EXTRACTED---------------------------------------------",elements)

            chunks = await self.chunk_elements(elements)

            print(f"CHUNKS CREATED: {len(chunks)}")

            embeddings = await asyncio.to_thread(embed_texts,
                [chunk.text for chunk in chunks]
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
                        content=chunk.text,
                        embedding=embedding,
                        company_id=self.document.company_id,
                        meta_data={
                            "category": type(chunk).__name__,
                            "page_number": chunk.metadata.page_number
                        }
                    )
                )

            self.document.status = "ready"

            await self.db.commit()

        except Exception as e:
            print(f"INGESTION FAILED for document {self.document.id}: {e!r}")
            await self.db.rollback()

            self.document.status = "failed"
            await self.db.commit()
