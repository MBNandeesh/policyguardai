from fastapi import APIRouter, HTTPException

from app.regulatory.service import (
    get_document,
    get_provision,
    get_source,
    list_documents,
    list_provisions,
    list_sources,
    search_provisions,
)

router = APIRouter()


@router.get("/regulatory-sources")
def regulatory_sources():
    return list_sources()


@router.get("/regulations")
def regulations():
    return list_documents()


@router.get("/regulations/search")
def regulation_search(q: str):
    if not q or not q.strip():
        return []
    return search_provisions(q)


@router.get("/regulations/{document_id}")
def regulation_detail(document_id: str):
    document = get_document(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Regulatory document not found")
    return document


@router.get("/regulations/{document_id}/provisions")
def regulation_provisions(document_id: str):
    document = get_document(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Regulatory document not found")
    return list_provisions(document_id=document_id)


@router.get("/regulations/{document_id}/provisions/{provision_id}")
def regulation_provision(document_id: str, provision_id: str):
    provision = get_provision(provision_id)
    if provision is None or provision.get("document_id") != document_id:
        raise HTTPException(status_code=404, detail="Provision not found")
    return provision
