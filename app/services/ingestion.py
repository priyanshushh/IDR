from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

class PDFProcessor:
    def __init__(self, file_path: str) -> None:
        self.file_path = file_path

    def extract_text_from_pdf(self) -> str:
        loader = PyPDFLoader(file_path=self.file_path)
        pages = loader.load()
        return "\n\n".join(page.page_content for page in pages)

    def chunk_text(self, text: str) -> list[dict[str, str]]:
        splitter = RecursiveCharacterTextSplitter(
            separators=["\n\n", "\n", ".", " "],
            chunk_size=500,
            chunk_overlap=25,
        )
        chunks = splitter.split_text(text)

        return [
            {
                "text": chunk,
            }
            for chunk in chunks
        ]
    