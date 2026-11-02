import fitz
from docx import Document


def extract_pdf(file_path: str):

    document = fitz.open(file_path)

    pages = []

    for page_number, page in enumerate(document, start=1):

        text = page.get_text()

        pages.append({
            "page_number": page_number,
            "text": text
        })

    document.close()

    return pages


def extract_docx(file_path: str):

    document = Document(file_path)

    paragraphs = []

    for paragraph in document.paragraphs:

        text = paragraph.text.strip()

        if text:
            paragraphs.append(text)

    return [
        {
            "page_number": None,
            "text": "\n".join(paragraphs)
        }
    ]


def parse_document(file_path: str, file_type: str):

    if file_type == "pdf":
        return extract_pdf(file_path)

    elif file_type == "docx":
        return extract_docx(file_path)

    else:
        raise ValueError("Unsupported document type")