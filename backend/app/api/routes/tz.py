from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from backend.app.schemas.tz import (
    TemplateDetailResponse,
    TemplatesResponse,
    TZCreateRequest,
    TZDocumentResponse,
    TZDocumentSummary,
    TZGenerateRequest,
    TZListResponse,
    TZTemplateSummary,
    TZUpdateRequest,
)
from backend.app.services.documents import document_export_service
from backend.app.services.tz_generator import tz_generator
from backend.app.services.tz_repository import tz_repository
from backend.app.services.tz_templates import tz_template_service


router = APIRouter()


# --- Шаблоны ------------------------------------------------------------------

@router.get("/templates", response_model=TemplatesResponse)
def list_templates() -> TemplatesResponse:
    templates = tz_template_service.list_templates()
    return TemplatesResponse(
        templates=[
            TZTemplateSummary(
                key=t.key,
                name=t.name,
                product_id=t.product_id,
                description=t.description,
                section_count=len(t.sections),
            )
            for t in templates
        ]
    )


@router.get("/templates/{key}", response_model=TemplateDetailResponse)
def get_template(key: str) -> TemplateDetailResponse:
    template = tz_template_service.get_template(key)
    if template is None:
        raise HTTPException(status_code=404, detail="Шаблон не найден")
    return TemplateDetailResponse(template=template)


# --- Документы ТЗ -------------------------------------------------------------

@router.get("", response_model=TZListResponse)
async def list_documents() -> TZListResponse:
    documents = await tz_repository.list()
    return TZListResponse(
        documents=[
            TZDocumentSummary(
                id=d.id,
                template_key=d.template_key,
                template_name=d.template_name,
                title=d.title,
                object_name=d.object_name,
                customer_name=d.customer_name,
                status=d.status,
                ready_score=d.ready_score,
                updated_at=d.updated_at.isoformat() if d.updated_at else None,
            )
            for d in documents
        ]
    )


@router.post("", response_model=TZDocumentResponse)
async def create_document(payload: TZCreateRequest) -> TZDocumentResponse:
    template = tz_template_service.get_template(payload.template_key)
    if template is None:
        raise HTTPException(status_code=404, detail="Шаблон не найден")

    document = tz_generator.new_document(
        template,
        title=payload.title,
        object_name=payload.object_name,
        customer_name=payload.customer_name,
        executor_name=payload.executor_name,
        contract_name=payload.contract_name,
        product_id=payload.product_id,
        input_data=payload.input_data,
        requisites=payload.requisites,
    )
    if payload.auto_fill:
        tz_generator.generate(document, mode="augment", template=template)

    await tz_repository.create(document)
    return TZDocumentResponse(document=document)


@router.get("/{doc_id}", response_model=TZDocumentResponse)
async def get_document(doc_id: str) -> TZDocumentResponse:
    document = await tz_repository.get(doc_id)
    if document is None:
        raise HTTPException(status_code=404, detail="ТЗ не найдено")
    return TZDocumentResponse(document=document)


@router.put("/{doc_id}", response_model=TZDocumentResponse)
async def update_document(doc_id: str, payload: TZUpdateRequest) -> TZDocumentResponse:
    document = await tz_repository.get(doc_id)
    if document is None:
        raise HTTPException(status_code=404, detail="ТЗ не найдено")

    data = payload.model_dump(exclude_unset=True)
    for field in ("title", "object_name", "customer_name", "executor_name", "contract_name", "status"):
        if field in data and data[field] is not None:
            setattr(document, field, data[field])
    if payload.input_data is not None:
        document.input_data = payload.input_data
    if payload.requisites is not None:
        document.requisites = {**document.requisites, **payload.requisites}
    if payload.sections is not None:
        document.sections = payload.sections

    document.ready_score = tz_generator.compute_ready_score(document)
    document.updated_at = datetime.now(timezone.utc)
    await tz_repository.update(document)
    return TZDocumentResponse(document=document)


@router.delete("/{doc_id}")
async def delete_document(doc_id: str) -> dict:
    ok = await tz_repository.delete(doc_id)
    if not ok:
        raise HTTPException(status_code=404, detail="ТЗ не найдено")
    return {"ok": True}


@router.post("/{doc_id}/generate", response_model=TZDocumentResponse)
async def generate_document(doc_id: str, payload: TZGenerateRequest) -> TZDocumentResponse:
    document = await tz_repository.get(doc_id)
    if document is None:
        raise HTTPException(status_code=404, detail="ТЗ не найдено")

    template = tz_template_service.get_or_default(document.template_key)
    tz_generator.generate(
        document,
        mode=payload.mode,
        instruction=payload.instruction,
        section_keys=payload.section_keys,
        template=template,
    )
    await tz_repository.update(document)
    return TZDocumentResponse(document=document)


@router.get("/{doc_id}/export")
async def export_document(doc_id: str) -> FileResponse:
    document = await tz_repository.get(doc_id)
    if document is None:
        raise HTTPException(status_code=404, detail="ТЗ не найдено")
    path = document_export_service.export_docx(document)
    return FileResponse(
        path=path,
        filename=path.name,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
