import hashlib
import json
import os
from typing import Any, Dict, List, Optional

from app.config import settings

STORAGE_ROOT = os.path.join(settings.storage_path, "regulatory")


def ensure_directories() -> None:
    os.makedirs(os.path.join(STORAGE_ROOT, "sources"), exist_ok=True)
    os.makedirs(os.path.join(STORAGE_ROOT, "documents"), exist_ok=True)
    os.makedirs(os.path.join(STORAGE_ROOT, "provisions"), exist_ok=True)


def _hash_text(value: str | None) -> str:
    payload = (value or "").strip()
    return hashlib.sha256(payload.encode("utf-8")).hexdigest() if payload else ""


def _source_file(source_id: str) -> str:
    return os.path.join(STORAGE_ROOT, "sources", f"{source_id}.json")


def _document_file(document_id: str) -> str:
    return os.path.join(STORAGE_ROOT, "documents", f"{document_id}.json")


def _provision_file(provision_id: str) -> str:
    return os.path.join(STORAGE_ROOT, "provisions", f"{provision_id}.json")


def _write_json(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)
    return payload


def _load_json(path: str) -> Optional[Dict[str, Any]]:
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _iter_records(folder: str) -> List[Dict[str, Any]]:
    if not os.path.exists(folder):
        return []
    records: List[Dict[str, Any]] = []
    for filename in sorted(os.listdir(folder)):
        if not filename.endswith(".json"):
            continue
        payload = _load_json(os.path.join(folder, filename))
        if payload:
            records.append(payload)
    return records


def _validate_source_payload(payload: Dict[str, Any]) -> None:
    source_domain = str(payload.get("source_domain") or "REGULATORY_AUTHORITY")
    if source_domain != "REGULATORY_AUTHORITY":
        raise ValueError("User document evidence cannot become a regulatory authority source.")

    authority_level = str(payload.get("authority_level") or "")
    source_type = str(payload.get("source_type") or "")
    if authority_level == "SECONDARY_SOURCE" and source_type in {"GFR", "PROCUREMENT_MANUAL"}:
        raise ValueError("Secondary sources are not accepted as authoritative regulatory sources for this phase.")

    if source_type == "GFR" and payload.get("issuing_authority", "").lower() not in {
        "department of expenditure",
        "ministry of finance",
        "government of india",
    }:
        raise ValueError("GFR source must identify an official Government of India authority.")

    if source_type == "OFFICIAL_PORTAL" and not payload.get("official_url"):
        raise ValueError("Official portal sources require an official URL.")

    if payload.get("title") == "Wikipedia Summary":
        raise ValueError("Unsupported source rejected: unofficial source cannot be treated as regulatory authority.")


def _validate_document_payload(payload: Dict[str, Any]) -> None:
    source_id = payload.get("source_id")
    if not source_id or not os.path.exists(_source_file(source_id)):
        raise ValueError("Document must reference a valid regulatory source.")


def create_source(
    *,
    title: str,
    issuing_authority: str,
    jurisdiction: str,
    government_level: str,
    source_type: str,
    authority_level: str,
    official_url: str = "",
    publication_date: str = "",
    effective_date: str = "",
    version: str = "UNKNOWN",
    status: str = "UNKNOWN",
    ingestion_status: str = "SOURCE_REQUIRED",
    source_domain: str = "REGULATORY_AUTHORITY",
) -> Dict[str, Any]:
    ensure_directories()
    normalized_title = (title or "").strip()
    if not normalized_title:
        raise ValueError("Source title is required.")

    for candidate in _iter_records(os.path.join(STORAGE_ROOT, "sources")):
        if (
            candidate.get("title") == normalized_title
            and candidate.get("issuing_authority") == issuing_authority
            and candidate.get("source_type") == source_type
        ):
            raise ValueError("Source already exists for the same title, authority, and type.")

    payload = {
        "source_id": os.urandom(8).hex(),
        "title": normalized_title,
        "issuing_authority": issuing_authority,
        "jurisdiction": jurisdiction,
        "government_level": government_level,
        "source_type": source_type,
        "authority_level": authority_level,
        "official_url": official_url,
        "publication_date": publication_date,
        "effective_date": effective_date,
        "version": version,
        "retrieved_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        "status": status,
        "ingestion_status": ingestion_status,
        "content_hash": _hash_text(f"{title}|{official_url}|{version}|{effective_date}"),
        "source_domain": source_domain,
    }
    _validate_source_payload(payload)
    _write_json(_source_file(payload["source_id"]), payload)
    return payload


def get_source(source_id: str) -> Optional[Dict[str, Any]]:
    return _load_json(_source_file(source_id))


def list_sources() -> List[Dict[str, Any]]:
    return sorted(_iter_records(os.path.join(STORAGE_ROOT, "sources")), key=lambda item: item.get("title", "").lower())


def create_document(
    *,
    source_id: str,
    title: str,
    issuing_authority: str,
    jurisdiction: str,
    government_level: str,
    document_type: str,
    version: str,
    publication_date: str,
    effective_date: str,
    official_url: str,
    status: str,
    ingestion_status: str,
) -> Dict[str, Any]:
    ensure_directories()
    source = get_source(source_id)
    if not source:
        raise ValueError("Cannot create a document without a valid source.")

    payload = {
        "document_id": os.urandom(8).hex(),
        "source_id": source_id,
        "title": title,
        "issuing_authority": issuing_authority,
        "jurisdiction": jurisdiction,
        "government_level": government_level,
        "document_type": document_type,
        "version": version,
        "publication_date": publication_date,
        "effective_date": effective_date,
        "retrieved_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        "official_url": official_url,
        "content_hash": _hash_text(f"{title}|{source_id}|{version}|{official_url}"),
        "status": status,
        "ingestion_status": ingestion_status,
    }
    _validate_document_payload(payload)
    _write_json(_document_file(payload["document_id"]), payload)
    return payload


def get_document(document_id: str) -> Optional[Dict[str, Any]]:
    return _load_json(_document_file(document_id))


def list_documents() -> List[Dict[str, Any]]:
    return sorted(_iter_records(os.path.join(STORAGE_ROOT, "documents")), key=lambda item: item.get("title", "").lower())


def create_provision(
    *,
    document_id: str,
    source_id: str,
    parent_id: Optional[str],
    provision_type: str,
    provision_number: str,
    heading: str,
    text: str,
    raw_text: str,
    normalized_text: str,
    page_number: Optional[int],
    source_locator: Optional[str],
    official_url: str,
    status: str = "ACTIVE",
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    ensure_directories()
    document = get_document(document_id)
    if not document:
        raise ValueError("Provision must belong to an existing document.")
    source = get_source(source_id)
    if not source:
        raise ValueError("Provision must reference a valid source.")

    payload = {
        "provision_id": os.urandom(8).hex(),
        "document_id": document_id,
        "source_id": source_id,
        "parent_id": parent_id,
        "provision_type": provision_type,
        "provision_number": provision_number,
        "heading": heading,
        "text": text,
        "raw_text": raw_text,
        "normalized_text": normalized_text,
        "page_number": page_number,
        "source_locator": source_locator,
        "official_url": official_url,
        "content_hash": _hash_text(raw_text or text),
        "status": status,
        "metadata": metadata or {},
    }
    _write_json(_provision_file(payload["provision_id"]), payload)
    return payload


def get_provision(provision_id: str) -> Optional[Dict[str, Any]]:
    return _load_json(_provision_file(provision_id))


def list_provisions(document_id: Optional[str] = None) -> List[Dict[str, Any]]:
    records = _iter_records(os.path.join(STORAGE_ROOT, "provisions"))
    if document_id:
        records = [item for item in records if item.get("document_id") == document_id]
    return sorted(records, key=lambda item: (item.get("page_number") or 0, item.get("provision_number", "")))


def search_provisions(q: str) -> List[Dict[str, Any]]:
    query = (q or "").strip().lower()
    if not query:
        return []

    results: List[Dict[str, Any]] = []
    for provision in list_provisions():
        document = get_document(provision["document_id"])
        if not document:
            continue
        if document.get("status") not in {"ACTIVE", "READY", "UNKNOWN"}:
            continue
        haystack = " ".join([
            provision.get("heading", ""),
            provision.get("text", ""),
            provision.get("normalized_text", ""),
            provision.get("provision_number", ""),
            document.get("title", ""),
        ]).lower()
        if query in haystack:
            results.append({
                "document_id": provision["document_id"],
                "document_title": document.get("title", ""),
                "provision_id": provision["provision_id"],
                "provision_number": provision.get("provision_number", ""),
                "heading": provision.get("heading", ""),
                "text": provision.get("text", ""),
                "page_number": provision.get("page_number"),
                "source_id": provision.get("source_id"),
                "official_url": provision.get("official_url", ""),
                "version": document.get("version", ""),
                "status": provision.get("status", "ACTIVE"),
            })
    return results
