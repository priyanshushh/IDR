import asyncio
from pathlib import Path

import pymupdf

from unstructured.partition.auto import partition
from unstructured.chunking.title import chunk_by_title
from unstructured.documents.elements import (
    Element,
    ElementMetadata,
    Image,
    NarrativeText,
    Table,
)

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
        # PDFs go through PyMuPDF instead of unstructured's partition_pdf: getting
        # unstructured to recognize tables requires strategy="hi_res"
        if self.file_path.suffix.lower() == ".pdf":
            return await asyncio.to_thread(self._extract_pdf_elements)

        return await asyncio.to_thread(partition, filename=str(self.file_path))

    def _extract_pdf_elements(self) -> list[Element]:
        elements: list[Element] = []
        with pymupdf.open(str(self.file_path)) as doc:
            for page_index, page in enumerate(doc):
                elements.extend(
                    self._extract_pdf_page_elements(page, page_index + 1)
                )
        return elements

    def _extract_pdf_page_elements(self, page, page_number: int) -> list[Element]:
       
        items: list[tuple[float, Element]] = []

        tables = page.find_tables()
        table_bboxes = [pymupdf.Rect(table.bbox) for table in tables.tables]

        for table in tables.tables:
            markdown = table.to_markdown().strip()
            if markdown:
                items.append((
                    table.bbox[1],
                    Table(text=markdown, metadata=ElementMetadata(page_number=page_number)),
                ))

        for x0, y0, x1, y1, text, _, block_type in page.get_text("blocks"):
            if block_type != 0:
                continue 

            text = text.strip()
            if not text:
                continue

            block_rect = pymupdf.Rect(x0, y0, x1, y1)
            if any(block_rect.intersects(bbox) for bbox in table_bboxes):
                continue

            items.append((
                y0,
                NarrativeText(text=text, metadata=ElementMetadata(page_number=page_number)),
            ))

        for image_info in page.get_image_info():
            items.append((
                image_info["bbox"][1],
                Image(text="[Image]", metadata=ElementMetadata(page_number=page_number)),
            ))

        items.sort(key=lambda item: item[0])
        return [element for _, element in items]


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
