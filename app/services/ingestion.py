from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from app.services.embeddings import embed_texts
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.documents import DocumentChunks, Document
from sqlalchemy import delete

class PDFProcessor:
    def __init__(self, file_path: str, db: AsyncSession,document:Document) -> None:
        self.file_path = Path("./uploads") / file_path
        self.db = db
        self.document = document

    def extract_text_from_pdf(self) -> list[Document]:

        loader = PyPDFLoader(file_path=self.file_path)
        pages = loader.load()

        return pages

    def chunk_text(self, text: str) -> list[dict[str, str]]:

        splitter = RecursiveCharacterTextSplitter(
            separators=["\n\n", "\n", ".", " "],
            chunk_size=500,
            chunk_overlap=25,
        )

        chunks = splitter.split_documents(text)
        return chunks

    async def process_document(self):
        try:
            self.document.status = "processing"
            await self.db.commit()
            text = self.extract_text_from_pdf()
            chunks = self.chunk_text(text)
            embeddings = embed_texts(
                [chunk.page_content for chunk in chunks]
            )

            await self.db.execute(
                delete(DocumentChunks).where(DocumentChunks.document_id == self.document.id)
            )

            for index, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                self.db.add(DocumentChunks(
                    document_id=self.document.id,
                    chunk_index=index,
                    content=chunk.page_content,
                    embedding=embedding,
                    company_id=self.document.company_id,
                ))

            self.document.status = "ready"
            await self.db.commit()

        except Exception as e:
            self.document.status = "failed"
            await self.db.commit()
            raise e