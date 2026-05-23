import shutil
from pathlib import Path

from markitdown import MarkItDown

from src.config import UPLOAD_DIR, CONVERTED_MD_DIR

_converter = MarkItDown()

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".pptx", ".html", ".htm", ".csv", ".txt", ".md"}

_DOCUMENT_TYPE_HINTS: dict[str, str] = {
    "policy": "policy_document",
    "procedure": "policy_document",
    "process": "policy_document",
    "technical": "technical_overview",
    "architecture": "technical_overview",
    "spec": "technical_overview",
    "product": "product_description",
    "brief": "product_description",
    "description": "product_description",
    "pitch": "product_description",
    "vendor": "product_description",
    "overview": "product_description",
    "transparency": "transparency_notice",
    "notice": "transparency_notice",
    "hr": "hr_document",
    "recruitment": "hr_document",
    "hiring": "hr_document",
}


def _infer_document_type(filename: str) -> str:
    lower = filename.lower()
    for keyword, doc_type in _DOCUMENT_TYPE_HINTS.items():
        if keyword in lower:
            return doc_type
    return "general_document"


def convert_file_to_markdown(file_path: Path) -> str:
    result = _converter.convert(str(file_path))
    return result.text_content or ""


def save_markdown(markdown_text: str, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown_text, encoding="utf-8")


def process_uploaded_files(files: list, session_id: str) -> list[dict]:
    """
    files: list of file-like objects (e.g. from st.file_uploader) or Path objects.
    Returns a list of dicts describing each processed document.
    """
    session_upload_dir = UPLOAD_DIR / session_id
    session_md_dir = CONVERTED_MD_DIR / session_id
    session_upload_dir.mkdir(parents=True, exist_ok=True)
    session_md_dir.mkdir(parents=True, exist_ok=True)

    results = []

    for f in files:
        # Accept both Streamlit UploadedFile objects and plain Path objects
        if isinstance(f, Path):
            file_path = f
            filename = f.name
        else:
            filename = f.name
            file_path = session_upload_dir / filename
            file_path.write_bytes(f.read())

        suffix = Path(filename).suffix.lower()
        if suffix not in SUPPORTED_EXTENSIONS:
            results.append(
                {
                    "filename": filename,
                    "session_id": session_id,
                    "markdown_path": None,
                    "document_type": "unsupported",
                    "error": f"Unsupported file type: {suffix}",
                }
            )
            continue

        try:
            markdown_text = convert_file_to_markdown(file_path)
            md_filename = Path(filename).stem + ".md"
            md_path = session_md_dir / md_filename
            save_markdown(markdown_text, md_path)

            results.append(
                {
                    "filename": filename,
                    "session_id": session_id,
                    "markdown_path": str(md_path),
                    "document_type": _infer_document_type(filename),
                    "error": None,
                }
            )
        except Exception as exc:
            results.append(
                {
                    "filename": filename,
                    "session_id": session_id,
                    "markdown_path": None,
                    "document_type": "unknown",
                    "error": str(exc),
                }
            )

    return results


def process_manual_description(text: str, session_id: str) -> dict:
    """
    Persist a free-text use-case description as markdown and return a doc dict
    compatible with chunk_document() / process_uploaded_files() output shape.
    """
    text = (text or "").strip()
    session_md_dir = CONVERTED_MD_DIR / session_id
    session_md_dir.mkdir(parents=True, exist_ok=True)

    filename = "manual_use_case_description.md"
    md_path = session_md_dir / filename
    markdown_text = f"# Manual use-case description\n\n{text}\n"
    save_markdown(markdown_text, md_path)

    return {
        "filename": filename,
        "session_id": session_id,
        "markdown_path": str(md_path),
        "document_type": "manual_description",
        "source_type": "user_input",
        "error": None,
    }
