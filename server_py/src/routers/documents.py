import io
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import MAX_DOC_CHARS_PER_FILE, MAX_DOC_SIZE_BYTES
from ..database import get_db
from ..dependencies import get_current_user
from ..models import Chat, Document

logger = logging.getLogger("app")

router = APIRouter(tags=["Documents"])

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md", ".text"}


def _extract_text(filename: str, data: bytes) -> str:
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        try:
            import pdfplumber
        except ImportError:
            raise HTTPException(
                status_code=500,
                detail="PDF support requires pdfplumber. Contact your administrator.",
            )
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            pages = [page.extract_text() or "" for page in pdf.pages]
        return "\n\n".join(p for p in pages if p.strip())

    elif ext == ".docx":
        try:
            from docx import Document as DocxDoc
        except ImportError:
            raise HTTPException(
                status_code=500,
                detail="DOCX support requires python-docx. Contact your administrator.",
            )
        doc = DocxDoc(io.BytesIO(data))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())

    elif ext in (".txt", ".md", ".text"):
        return data.decode("utf-8", errors="replace")

    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Supported: PDF, DOCX, TXT, MD.",
        )


@router.post("/api/chats/{chat_id}/documents")
async def upload_document(
    chat_id: int,
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Chat).where(Chat.id == chat_id, Chat.user_id == user["id"])
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Chat not found.")

    data = await file.read()
    if len(data) > MAX_DOC_SIZE_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds 20 MB limit.")

    text = _extract_text(file.filename or "upload", data)
    if not text.strip():
        raise HTTPException(
            status_code=422, detail="No readable text could be extracted from the file."
        )

    text = text[:MAX_DOC_CHARS_PER_FILE]

    doc = Document(
        chat_id=chat_id,
        user_id=user["id"],
        filename=file.filename or "upload",
        content_text=text,
        size_bytes=len(data),
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    logger.info(f"[Documents] Uploaded '{doc.filename}' ({len(text)} chars) to chat {chat_id}")
    return {
        "id": doc.id,
        "filename": doc.filename,
        "size_bytes": doc.size_bytes,
        "char_count": len(text),
        "excerpt": text[:200],
        "created_at": doc.created_at.isoformat(),
    }


@router.get("/api/chats/{chat_id}/documents")
async def list_documents(
    chat_id: int,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Chat).where(Chat.id == chat_id, Chat.user_id == user["id"])
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Chat not found.")

    rows = await db.execute(
        select(Document).where(Document.chat_id == chat_id).order_by(Document.created_at)
    )
    return [
        {
            "id": d.id,
            "filename": d.filename,
            "size_bytes": d.size_bytes,
            "char_count": len(d.content_text),
            "created_at": d.created_at.isoformat(),
        }
        for d in rows.scalars().all()
    ]


@router.delete("/api/documents/{doc_id}", status_code=204)
async def delete_document(
    doc_id: int,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Document).where(Document.id == doc_id, Document.user_id == user["id"])
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    await db.delete(doc)
    await db.commit()
