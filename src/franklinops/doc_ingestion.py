from __future__ import annotations

import csv
import hashlib
import json
import mimetypes
import os
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from pathlib import Path
from typing import Any, Iterable, Optional

from .audit import AuditLogger
from .opsdb import OpsDB


ALLOWED_EXTS = {".pdf", ".eml", ".csv", ".txt", ".docx", ".xlsx"}

# Files matching these patterns are NEVER ingested (credentials, secrets, login info).
# Use env vars / keyring for credentials; see SECURITY_SECRETS_POLICY.md
EXCLUDED_FILE_PATTERNS = (
    r"(?i)login\.txt$",
    r"(?i)password\.txt$",
    r"(?i)credentials?\.txt$",
    r"(?i)secret[s]?\.txt$",
    r"(?i)procore\s*login",
    r"(?i)\.env$",
    r"(?i)\.env\.local$",
    r"(?i)\.env\.prod",
)


def _should_exclude_file(rel_path: str) -> bool:
    """Exclude credential/secret files from ingestion."""
    name = rel_path.replace("\\", "/").split("/")[-1]
    for pat in EXCLUDED_FILE_PATTERNS:
        if re.search(pat, name):
            return True
    return False


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def file_mtime_iso(path: Path) -> str:
    stat = path.stat()
    return datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()


def _compute_hash_bytes(path: Path) -> str:
    try:
        import blake3  # type: ignore

        h = blake3.blake3()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()


def _strip_html(html_text: str) -> str:
    # Keep this dependency-free; good enough for invoice/reminder emails.
    txt = re.sub(r"(?is)<(script|style).*?>.*?</\\1>", " ", html_text)
    txt = re.sub(r"(?is)<br\\s*/?>", "\n", txt)
    txt = re.sub(r"(?is)</p\\s*>", "\n", txt)
    txt = re.sub(r"(?is)<[^>]+>", " ", txt)
    txt = re.sub(r"[ \\t\\f\\v]+", " ", txt)
    txt = re.sub(r"\\n{3,}", "\n\n", txt)
    return txt.strip()


def extract_text_from_txt(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def extract_text_from_csv(path: Path) -> str:
    out_lines: list[str] = []
    with open(path, "r", encoding="utf-8", errors="replace", newline="") as f:
        try:
            sample = f.read(4096)
            f.seek(0)
            dialect = csv.Sniffer().sniff(sample)
        except Exception:
            dialect = csv.excel
        reader = csv.reader(f, dialect)
        for row in reader:
            out_lines.append(", ".join(cell.strip() for cell in row))
    return "\n".join(out_lines).strip()


def extract_text_from_eml(path: Path) -> str:
    raw = path.read_bytes()
    msg = BytesParser(policy=policy.default).parsebytes(raw)

    headers = [
        f"Subject: {msg.get('subject', '')}",
        f"From: {msg.get('from', '')}",
        f"To: {msg.get('to', '')}",
        f"Date: {msg.get('date', '')}",
    ]

    parts_text: list[str] = []
    if msg.is_multipart():
        for part in msg.walk():
            ctype = (part.get_content_type() or "").lower()
            if ctype in {"text/plain", "text/html"}:
                try:
                    content = part.get_content()
                except Exception:
                    continue
                if not isinstance(content, str):
                    continue
                parts_text.append(_strip_html(content) if ctype == "text/html" else content.strip())
    else:
        try:
            content = msg.get_content()
        except Exception:
            content = ""
        if isinstance(content, str):
            parts_text.append(content.strip())

    body = "\n\n".join(t for t in parts_text if t)
    return ("\n".join(headers) + "\n\n" + body).strip()


def extract_text_from_docx(path: Path) -> str:
    try:
        from docx import Document  # type: ignore
    except Exception as e:
        raise RuntimeError("DOCX ingestion requires 'python-docx' (pip install python-docx).") from e

    doc = Document(str(path))
    out: list[str] = []

    for p in getattr(doc, "paragraphs", []) or []:
        t = (getattr(p, "text", "") or "").strip()
        if t:
            out.append(t)

    for tbl in getattr(doc, "tables", []) or []:
        for row in getattr(tbl, "rows", []) or []:
            cells: list[str] = []
            for cell in getattr(row, "cells", []) or []:
                ct = (getattr(cell, "text", "") or "").strip()
                if ct:
                    cells.append(ct)
            if cells:
                out.append(" | ".join(cells))

    return "\n".join(out).strip()


def extract_text_from_xlsx(path: Path) -> str:
    try:
        import openpyxl  # type: ignore
    except Exception as e:
        raise RuntimeError("XLSX ingestion requires 'openpyxl' (pip install openpyxl).") from e

    # Keep extraction bounded for large sheets.
    try:
        max_rows = int(float(os.getenv("FRANKLINOPS_XLSX_MAX_ROWS", "5000")))
    except Exception:
        max_rows = 5000
    try:
        max_chars = int(float(os.getenv("FRANKLINOPS_XLSX_MAX_CHARS", "200000")))
    except Exception:
        max_chars = 200000

    wb = openpyxl.load_workbook(str(path), data_only=True, read_only=True)
    out_lines: list[str] = []
    total_chars = 0

    try:
        for ws in wb.worksheets:
            out_lines.append(f"Sheet: {ws.title}")
            row_count = 0
            for row in ws.iter_rows(values_only=True):
                row_count += 1
                if max_rows > 0 and row_count > max_rows:
                    out_lines.append("[... rows truncated ...]")
                    break

                cells: list[str] = []
                for v in row:
                    cells.append("" if v is None else str(v).strip())
                line = "\t".join(cells).rstrip()
                if not line:
                    continue
                out_lines.append(line)
                total_chars += len(line)
                if max_chars > 0 and total_chars >= max_chars:
                    out_lines.append("[... content truncated ...]")
                    break
    finally:
        try:
            wb.close()
        except Exception as e:
            import logging
            logging.getLogger("franklinops.doc_ingestion").debug("xlsx close: %s", e)

    return "\n".join(out_lines).strip()


def extract_text_from_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception as e:
        raise RuntimeError("PDF ingestion requires 'pypdf' (pip install pypdf).") from e

    # Large plan sets can be thousands of pages; keep ingestion bounded by default.
    # You can override these with env vars if you want full-text extraction.
    try:
        max_pages = int(float(os.getenv("FRANKLINOPS_PDF_MAX_PAGES", "40")))
    except Exception:
        max_pages = 40
    try:
        max_chars = int(float(os.getenv("FRANKLINOPS_PDF_MAX_CHARS", "200000")))
    except Exception:
        max_chars = 200000

    reader = PdfReader(str(path))
    texts: list[str] = []
    total_chars = 0
    for i, page in enumerate(reader.pages):
        if max_pages > 0 and i >= max_pages:
            break
        try:
            t = page.extract_text() or ""
        except Exception:
            t = ""
        t = t.strip()
        if not t:
            continue
        texts.append(t)
        total_chars += len(t)
        if max_chars > 0 and total_chars >= max_chars:
            break
    return "\n\n".join(texts).strip()


def extract_text(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".txt":
        return extract_text_from_txt(path)
    if ext == ".csv":
        return extract_text_from_csv(path)
    if ext == ".eml":
        return extract_text_from_eml(path)
    if ext == ".docx":
        return extract_text_from_docx(path)
    if ext == ".xlsx":
        return extract_text_from_xlsx(path)
    if ext == ".pdf":
        return extract_text_from_pdf(path)
    raise ValueError(f"unsupported extension: {ext}")


@dataclass(frozen=True)
class IngestResult:
    source: str
    rel_path: str
    status: str  # new | modified | unchanged | failed
    artifact_id: Optional[str] = None
    birthmark: Optional[str] = None
    error: str = ""


def iter_files(root: Path, *, allowed_exts: set[str] = ALLOWED_EXTS, exclude_dirs: Optional[set[str]] = None) -> Iterable[tuple[Path, str]]:
    exclude_dirs = exclude_dirs or {"__pycache__", ".git", ".venv", "venv", "node_modules"}
    root = root.resolve()

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in exclude_dirs]
        for name in filenames:
            p = Path(dirpath) / name
            if p.suffix.lower() not in allowed_exts:
                continue
            try:
                rel = p.relative_to(root).as_posix()
            except Exception:
                rel = str(p)
            if _should_exclude_file(rel):
                continue
            yield p, rel


class DocumentIngestor:
    def __init__(self, db: OpsDB, audit: AuditLogger):
        self._db = db
        self._audit = audit

    def ingest_file(self, *, source: str, abs_path: Path, rel_path: str) -> IngestResult:
        stat = abs_path.stat()
        size_bytes = int(stat.st_size)
        modified_at = file_mtime_iso(abs_path)
        content_type = (mimetypes.guess_type(str(abs_path))[0] or "").strip()

        row = self._db.conn.execute(
            """
            SELECT id, birthmark, size_bytes, modified_at
            FROM artifacts
            WHERE source = ? AND path = ?
            """,
            (source, rel_path),
        ).fetchone()

        if row and int(row["size_bytes"] or 0) == size_bytes and (row["modified_at"] or "") == modified_at:
            return IngestResult(source=source, rel_path=rel_path, status="unchanged", artifact_id=row["id"], birthmark=row["birthmark"])

        try:
            birthmark = _compute_hash_bytes(abs_path)
            existing_birthmark = (row["birthmark"] if row else "") or ""
            if row and existing_birthmark == birthmark:
                with self._db.tx() as conn:
                    conn.execute(
                        """
                        UPDATE artifacts
                        SET size_bytes = ?, modified_at = ?, ingested_at = ?, status = ?, content_type = ?,
                            metadata_json = ?
                        WHERE id = ?
                        """,
                        (
                            size_bytes,
                            modified_at,
                            utcnow_iso(),
                            "ingested",
                            content_type,
                            json.dumps({"abs_path": str(abs_path)}, ensure_ascii=False),
                            row["id"],
                        ),
                    )
                return IngestResult(source=source, rel_path=rel_path, status="unchanged", artifact_id=row["id"], birthmark=birthmark)

            extracted = extract_text(abs_path)
            now = utcnow_iso()
            metadata = {"abs_path": str(abs_path), "ext": abs_path.suffix.lower()}

            if row:
                artifact_id = row["id"]
                with self._db.tx() as conn:
                    conn.execute(
                        """
                        UPDATE artifacts
                        SET content_type = ?, birthmark = ?, size_bytes = ?, modified_at = ?, ingested_at = ?,
                            status = ?, extracted_text = ?, metadata_json = ?
                        WHERE id = ?
                        """,
                        (
                            content_type,
                            birthmark,
                            size_bytes,
                            modified_at,
                            now,
                            "ingested",
                            extracted,
                            json.dumps(metadata, ensure_ascii=False),
                            artifact_id,
                        ),
                    )
                self._audit.append(
                    actor="system",
                    action="artifact_ingested",
                    scope="internal",
                    entity_type="artifact",
                    entity_id=artifact_id,
                    details={"source": source, "path": rel_path, "status": "modified"},
                )
                return IngestResult(source=source, rel_path=rel_path, status="modified", artifact_id=artifact_id, birthmark=birthmark)

            artifact_id = uuid.uuid4().hex
            with self._db.tx() as conn:
                conn.execute(
                    """
                    INSERT INTO artifacts (
                      id, source, path, content_type, birthmark, size_bytes, modified_at,
                      ingested_at, status, extracted_text, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        artifact_id,
                        source,
                        rel_path,
                        content_type,
                        birthmark,
                        size_bytes,
                        modified_at,
                        now,
                        "ingested",
                        extracted,
                        json.dumps(metadata, ensure_ascii=False),
                    ),
                )
            self._audit.append(
                actor="system",
                action="artifact_ingested",
                scope="internal",
                entity_type="artifact",
                entity_id=artifact_id,
                details={"source": source, "path": rel_path, "status": "new"},
            )
            return IngestResult(source=source, rel_path=rel_path, status="new", artifact_id=artifact_id, birthmark=birthmark)

        except Exception as e:
            now = utcnow_iso()
            metadata = {"abs_path": str(abs_path), "error": str(e), "ext": abs_path.suffix.lower()}
            if row:
                with self._db.tx() as conn:
                    conn.execute(
                        """
                        UPDATE artifacts
                        SET ingested_at = ?, status = ?, metadata_json = ?
                        WHERE id = ?
                        """,
                        (now, "failed", json.dumps(metadata, ensure_ascii=False), row["id"]),
                    )
                artifact_id = row["id"]
            else:
                artifact_id = uuid.uuid4().hex
                with self._db.tx() as conn:
                    conn.execute(
                        """
                        INSERT INTO artifacts (id, source, path, ingested_at, status, metadata_json)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (artifact_id, source, rel_path, now, "failed", json.dumps(metadata, ensure_ascii=False)),
                    )

            self._audit.append(
                actor="system",
                action="artifact_ingest_failed",
                scope="internal",
                entity_type="artifact",
                entity_id=artifact_id,
                details={"source": source, "path": rel_path, "error": str(e)},
            )
            return IngestResult(source=source, rel_path=rel_path, status="failed", artifact_id=artifact_id, error=str(e))


def ingest_roots(db: OpsDB, audit: AuditLogger, *, roots: dict[str, str]) -> dict[str, Any]:
    ingestor = DocumentIngestor(db, audit)
    results: list[IngestResult] = []
    seen: dict[str, set[str]] = {}
    scanned_sources: set[str] = set()

    for source, root_str in roots.items():
        if not root_str:
            continue
        root = Path(root_str)
        if not root.exists():
            audit.append(actor="system", action="ingest_root_missing", details={"source": source, "root": root_str})
            continue
        scanned_sources.add(source)
        seen.setdefault(source, set())
        for abs_path, rel_path in iter_files(root):
            seen[source].add(rel_path)
            results.append(ingestor.ingest_file(source=source, abs_path=abs_path, rel_path=rel_path))

    # Mark missing artifacts (deletions) for scanned sources
    now = utcnow_iso()
    for source in sorted(scanned_sources):
        rows = db.conn.execute(
            "SELECT id, path, status FROM artifacts WHERE source = ?",
            (source,),
        ).fetchall()
        present = seen.get(source, set())
        missing = [r for r in rows if (r["path"] or "") not in present]
        if not missing:
            continue
        with db.tx() as conn:
            for r in missing:
                # Keep a stable "missing" state; do not overwrite "failed" unless you want an operator to re-check it.
                if (r["status"] or "") in {"missing"}:
                    continue
                conn.execute(
                    "UPDATE artifacts SET status = ?, ingested_at = ?, metadata_json = ? WHERE id = ?",
                    ("missing", now, json.dumps({"note": "not found during scan"}, ensure_ascii=False), r["id"]),
                )
                audit.append(
                    actor="system",
                    action="artifact_missing",
                    scope="internal",
                    entity_type="artifact",
                    entity_id=r["id"],
                    details={"source": source, "path": r["path"]},
                )

    counts = {"new": 0, "modified": 0, "unchanged": 0, "failed": 0}
    for r in results:
        if r.status in counts:
            counts[r.status] += 1

    return {"counts": counts, "results": [r.__dict__ for r in results]}

