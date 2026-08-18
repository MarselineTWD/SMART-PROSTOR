import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from backend.app.core.config import settings
from backend.app.models.domain import TZDocumentSection

from backend.app.schemas.tz import (
    TemplateDetailResponse,
    TemplatesResponse,
    TZChatApplyRequest,
    TZChatApplyResponse,
    TZChatHistoryResponse,
    TZChatSendRequest,
    TZChatSendResponse,
    TZCreateRequest,
    TZDocumentResponse,
    TZDocumentSummary,
    TZGenerateRequest,
    TZListResponse,
    TZTemplateSummary,
    TZSwitchTemplateRequest,
    TZValidationResult,
    TZUpdateRequest,
)
from backend.app.core.config import settings
from backend.app.services.assistant import assistant_service
from backend.app.services.documents import document_export_service
from backend.app.services.tz_chat import tz_chat_service
from backend.app.services.storage import DOCX_MIME, get_storage_service
from backend.app.services.tz_generator import tz_generator
from backend.app.services.tz_repository import tz_repository
from backend.app.services.tz_templates import tz_template_service
from backend.app.services.tz_validation import tz_validation_service


logger = logging.getLogger(__name__)


router = APIRouter()


def _document_response(document) -> TZDocumentResponse:
    validation = tz_validation_service.validate(document)
    document.ready_score = validation.ready_score
    return TZDocumentResponse(document=document, validation=validation)


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
                source_files=t.source_files,
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
    validation = tz_validation_service.validate(document)
    document.ready_score = validation.ready_score
    await tz_repository.update(document)
    return TZDocumentResponse(document=document, validation=validation)


@router.get("/{doc_id}", response_model=TZDocumentResponse)
async def get_document(doc_id: str) -> TZDocumentResponse:
    document = await tz_repository.get(doc_id)
    if document is None:
        raise HTTPException(status_code=404, detail="ТЗ не найдено")
    return _document_response(document)


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

    document.ready_score = tz_validation_service.validate(document).ready_score
    document.updated_at = datetime.now(timezone.utc)
    await tz_repository.update(document)
    return _document_response(document)


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
    validation = tz_validation_service.validate(document)
    document.ready_score = validation.ready_score
    await tz_repository.update(document)
    return TZDocumentResponse(document=document, validation=validation)


@router.post("/{doc_id}/validate", response_model=TZValidationResult)
async def validate_document(doc_id: str) -> TZValidationResult:
    document = await tz_repository.get(doc_id)
    if document is None:
        raise HTTPException(status_code=404, detail="ТЗ не найдено")
    validation = tz_validation_service.validate(document)
    document.ready_score = validation.ready_score
    await tz_repository.update(document)
    return validation


@router.post("/{doc_id}/switch-template", response_model=TZDocumentResponse)
async def switch_document_template(doc_id: str, payload: TZSwitchTemplateRequest) -> TZDocumentResponse:
    document = await tz_repository.get(doc_id)
    if document is None:
        raise HTTPException(status_code=404, detail="ТЗ не найдено")
    template = tz_template_service.get_template(payload.template_key)
    if template is None:
        raise HTTPException(status_code=404, detail="Шаблон не найден")

    previous = {section.key: section for section in document.sections}
    document.sections = [
        previous.get(section.key) or TZDocumentSection(
            key=section.key, title=section.title, content="", source="template"
        )
        for section in template.sections
    ]
    for section in document.sections:
        template_section = next((s for s in template.sections if s.key == section.key), None)
        if template_section:
            section.title = template_section.title
    document.template_key = template.key
    document.template_name = template.name
    document.product_id = template.product_id
    document.requisites["stages"] = list(template.stage_presets)
    document.updated_at = datetime.now(timezone.utc)
    validation = tz_validation_service.validate(document)
    document.ready_score = validation.ready_score
    await tz_repository.update(document)
    return TZDocumentResponse(document=document, validation=validation)


@router.get("/{doc_id}/export")
async def export_document(doc_id: str) -> FileResponse:
    """Собирает docx, кладёт в MinIO (bucket `prostor-tz`) и отдаёт файл.

    Ключ хранилища сохраняется в `tz_documents.storage_key`, чтобы позже
    можно было переиспользовать тот же объект через presigned URL без
    повторной генерации.
    """
    document = await tz_repository.get(doc_id)
    if document is None:
        raise HTTPException(status_code=404, detail="ТЗ не найдено")

    path = document_export_service.export_docx(document)

    # Заливаем в объектное хранилище; если MinIO недоступен, просто
    # отдаём файл — не ломаем демо-путь.
    try:
        storage = get_storage_service()
        key = f"{doc_id}/{path.name}"
        await storage.aput_file(settings.s3_bucket_tz, key, path, DOCX_MIME)
        document.storage_key = key
        await tz_repository.update(document)
    except Exception as exc:
        logger.warning("MinIO upload failed for tz=%s: %s", doc_id, exc)

    return FileResponse(
        path=path,
        filename=path.name,
        media_type=DOCX_MIME,
    )


# --- Чат по документу ТЗ ------------------------------------------------------

def _chat_context(document, validation, extra: dict | None) -> dict:
    context = {
        "tz": {
            "id": document.id,
            "template_name": document.template_name,
            "ready_score": document.ready_score,
            "object_name": document.object_name,
            "customer_name": document.customer_name,
            "executor_name": document.executor_name,
            "goal": document.input_data.goal,
            "deadline": document.input_data.deadline,
        },
        "validation_issues": [i.model_dump() for i in validation.issues],
        "empty_sections": [s.title for s in document.sections if not s.content.strip()],
    }
    if extra:
        context.update(extra)
    return context


@router.get("/{doc_id}/chat", response_model=TZChatHistoryResponse)
async def get_chat(doc_id: str) -> TZChatHistoryResponse:
    document = await tz_repository.get(doc_id)
    if document is None:
        raise HTTPException(status_code=404, detail="ТЗ не найдено")
    template = tz_template_service.get_or_default(document.template_key)
    return TZChatHistoryResponse(
        messages=document.chat,
        allowed_fields=tz_chat_service.allowed_fields(document, template),
    )


@router.post("/{doc_id}/chat", response_model=TZChatSendResponse)
async def post_chat(doc_id: str, payload: TZChatSendRequest) -> TZChatSendResponse:
    document = await tz_repository.get(doc_id)
    if document is None:
        raise HTTPException(status_code=404, detail="ТЗ не найдено")
    template = tz_template_service.get_or_default(document.template_key)
    validation = tz_validation_service.validate(document)
    allowed = tz_chat_service.allowed_fields(document, template)
    history = [(m.role, m.text) for m in document.chat]

    document.chat.append(tz_chat_service.make_message("user", payload.message))
    reply, provider, fallback = assistant_service.generate(
        message=payload.message,
        context=_chat_context(document, validation, payload.context),
        history=history,
        allowed_fields=allowed,
    )
    assistant_message = tz_chat_service.make_message(
        "assistant",
        reply.reply,
        suggestions=reply.suggestions,
        field_updates=reply.field_updates,
        warnings=reply.warnings,
    )
    document.chat.append(assistant_message)

    validation = tz_validation_service.validate(document)
    document.ready_score = validation.ready_score
    document.updated_at = datetime.now(timezone.utc)
    await tz_repository.update(document)
    return TZChatSendResponse(
        message=assistant_message,
        provider=provider,
        model=settings.llm_model if provider == "deepseek" else None,
        fallback=fallback,
        validation=validation,
    )


@router.post("/{doc_id}/chat/apply", response_model=TZChatApplyResponse)
async def apply_chat(doc_id: str, payload: TZChatApplyRequest) -> TZChatApplyResponse:
    document = await tz_repository.get(doc_id)
    if document is None:
        raise HTTPException(status_code=404, detail="ТЗ не найдено")
    template = tz_template_service.get_or_default(document.template_key)

    applied, skipped = tz_chat_service.apply(document, template, payload.updates)
    if applied:
        _mark_applied(document, applied)
        note = f"ИИ перенёс в ТЗ значений: {len(applied)}."
        document.notes = [*[n for n in document.notes if not n.startswith("ИИ перенёс")], note]

    validation = tz_validation_service.validate(document)
    document.ready_score = validation.ready_score
    await tz_repository.update(document)
    return TZChatApplyResponse(
        document=document, validation=validation, applied=applied, skipped=skipped
    )


def _mark_applied(document, applied) -> None:
    """Помечает применённые правки в истории чата (для стабильного состояния UI)."""
    keys = {(u.target, u.key) for u in applied}
    for message in document.chat:
        for update in message.field_updates:
            if (update.target, update.key) in keys:
                update.applied = True


@router.get("/{doc_id}/download-url")
async def download_url(doc_id: str) -> dict:
    """Возвращает presigned URL для скачивания docx напрямую из MinIO."""
    document = await tz_repository.get(doc_id)
    if document is None:
        raise HTTPException(status_code=404, detail="ТЗ не найдено")

    storage = get_storage_service()

    # Если ещё не выгружали — сгенерируем docx и загрузим сейчас.
    key = document.storage_key
    if not key:
        path = document_export_service.export_docx(document)
        key = f"{doc_id}/{path.name}"
        try:
            await storage.aput_file(settings.s3_bucket_tz, key, path, DOCX_MIME)
            document.storage_key = key
            await tz_repository.update(document)
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail=f"Объектное хранилище недоступно: {exc}",
            )

    url = await storage.apresigned_url(settings.s3_bucket_tz, key)
    return {"url": url, "storage_key": key, "expires_in": settings.s3_presign_ttl}
