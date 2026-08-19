import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from backend.app.core.config import settings
from backend.app.models.domain import TZDocument, TZDocumentSection

from backend.app.schemas.tz import (
    TemplateDetailResponse,
    TemplatesResponse,
    TZChatApplyRequest,
    TZChatApplyResponse,
    TZChatHistoryResponse,
    TZChatSendRequest,
    TZChatSendResponse,
    TZCompleteRequest,
    TZCreateRequest,
    TZDocumentResponse,
    TZDocumentSummary,
    TZGenerateRequest,
    TZFeedbackRequest,
    TZPreviewGenerateRequest,
    TZListResponse,
    TZTemplateSummary,
    TZSwitchTemplateRequest,
    TZValidationResult,
    TZUpdateRequest,
)
from backend.app.services.assistant import assistant_service
from backend.app.services.assistant_context import collect_exceptional_conditions, enrich_assistant_context
from backend.app.services.documents import document_export_service
from backend.app.services.procurement import procurement_service
from backend.app.services.tz_chat import tz_chat_service
from backend.app.services.storage import DOCX_MIME, get_storage_service
from backend.app.services.tz_generator import tz_generator
from backend.app.services.tz_planning import sync_services
from backend.app.services.tz_repository import tz_repository
from backend.app.services.tz_templates import tz_template_service
from backend.app.services.tz_validation import tz_validation_service
from backend.app.schemas.contractors import ContractorAnalysisResponse


logger = logging.getLogger(__name__)


router = APIRouter()


def _document_response(document) -> TZDocumentResponse:
    sync_services(document, tz_template_service.get_or_default(document.template_key))
    validation = tz_validation_service.validate(document)
    document.ready_score = validation.ready_score
    return TZDocumentResponse(document=document, validation=validation)


def _preview_document(payload: TZCreateRequest):
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
    if payload.sections is not None:
        document.sections = payload.sections
    document.ai_initially_generated = payload.ai_initially_generated
    if payload.auto_fill:
        tz_generator.generate(document, mode="augment", template=template)
    return document


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


# --- Несохранённый конструктор ----------------------------------------------

@router.post("/preview", response_model=TZDocumentResponse)
def preview_document(payload: TZCreateRequest) -> TZDocumentResponse:
    """Создаёт модель ТЗ для UI, не записывая её в БД."""
    return _document_response(_preview_document(payload))


@router.post("/preview/generate", response_model=TZDocumentResponse)
async def generate_preview(payload: TZPreviewGenerateRequest) -> TZDocumentResponse:
    document = payload.document.model_copy(deep=True)
    template = tz_template_service.get_or_default(document.template_key)
    conditions = collect_exceptional_conditions(
        await tz_repository.list(),
        " ".join(filter(None, [document.title, document.object_name, document.input_data.goal])),
    )
    tz_generator.generate(
        document,
        mode=payload.mode,
        instruction=payload.instruction,
        section_keys=payload.section_keys,
        plan_only=payload.plan_only,
        knowledge_conditions=conditions,
        template=template,
    )
    return _document_response(document)


@router.post("/preview/validate", response_model=TZValidationResult)
def validate_preview(document: TZDocument) -> TZValidationResult:
    return tz_validation_service.validate(document)


@router.post("/complete", response_model=TZDocumentResponse)
async def complete_document(payload: TZCompleteRequest) -> TZDocumentResponse:
    """Фиксирует выбранного исполнителя и переводит полностью заполненное ТЗ в ready."""
    document = payload.document.model_copy(deep=True)
    analysis = procurement_service.estimate_for_tz(document, payload.additional_product_ids)
    estimate = analysis.get("estimate") or {}
    contractor = next(
        (item for item in estimate.get("companies", []) if item["company_id"] == payload.company_id),
        None,
    )
    if contractor is None:
        raise HTTPException(
            status_code=422,
            detail="Подрядчик больше не соответствует условиям ТЗ. Пересчитайте диаграмму Ганта.",
        )

    document.executor_name = contractor["company_name"]
    document.contract_name = contractor.get("contract_number") or document.contract_name
    document.requisites = {
        **document.requisites,
        "selected_contractor_id": contractor["company_id"],
        "selected_contractor": {
            "company_id": contractor["company_id"],
            "company_name": contractor["company_name"],
            "rating": contractor.get("rating"),
            "contract_number": contractor.get("contract_number", ""),
            "calc_id": contractor.get("calc_id", ""),
            "estimated_days": contractor["estimated_days"],
            "cost_without_vat": contractor["cost_without_vat"],
            "cost_with_vat": contractor["cost_with_vat"],
            "additional_product_ids": payload.additional_product_ids,
            "selected_at": datetime.now(timezone.utc).isoformat(),
        },
    }

    validation = tz_validation_service.validate(document)
    if not validation.valid or validation.ready_score < 100:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "ТЗ нужно заполнить на 100% до выбора исполнителя.",
                "ready_score": validation.ready_score,
                "issues": [issue.model_dump() for issue in validation.issues],
            },
        )

    document.status = "ready"
    document.ready_score = 100
    document.updated_at = datetime.now(timezone.utc)
    await tz_repository.update(document)
    return TZDocumentResponse(document=document, validation=validation)


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
                executor_name=d.executor_name,
                ai_initially_generated=d.ai_initially_generated,
                feedback=d.feedback,
                updated_at=d.updated_at.isoformat() if d.updated_at else None,
            )
            for d in documents
        ]
    )


@router.post("", response_model=TZDocumentResponse)
async def create_document(payload: TZCreateRequest) -> TZDocumentResponse:
    document = _preview_document(payload)

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
    if payload.ai_initially_generated is not None:
        document.ai_initially_generated = payload.ai_initially_generated

    document.ready_score = tz_validation_service.validate(document).ready_score
    document.updated_at = datetime.now(timezone.utc)
    await tz_repository.update(document)
    return _document_response(document)


@router.put("/{doc_id}/feedback", response_model=TZDocumentResponse)
async def update_feedback(doc_id: str, payload: TZFeedbackRequest) -> TZDocumentResponse:
    """Сохраняет оценки по завершённому ТЗ, не меняя его статус и содержимое."""
    document = await tz_repository.get(doc_id)
    if document is None:
        raise HTTPException(status_code=404, detail="ТЗ не найдено")
    if document.status != "ready":
        raise HTTPException(status_code=422, detail="Оценки доступны только для готового ТЗ")
    document.ai_initially_generated = payload.ai_initially_generated
    document.feedback = payload.feedback
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
    conditions = collect_exceptional_conditions(
        await tz_repository.list(),
        " ".join(filter(None, [document.title, document.object_name, document.input_data.goal])),
    )
    tz_generator.generate(
        document,
        mode=payload.mode,
        instruction=payload.instruction,
        section_keys=payload.section_keys,
        plan_only=payload.plan_only,
        knowledge_conditions=conditions,
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


@router.get("/{doc_id}/contractors", response_model=ContractorAnalysisResponse)
async def contractors_for_document(doc_id: str, top: int = 3) -> ContractorAnalysisResponse:
    """Топ-N подрядчиков под сохранённое ТЗ.

    Возвращает шорт-лист (по умолчанию 3) с готовыми данными для диаграммы
    Ганта (этапы с датами) и полной стоимостью в рублях, посчитанной по
    ставкам грейдов L2–L5 и составу команды продукта. Рекомендация
    объясняется полем `recommendation_reason`: fastest / cheapest / top_rated.
    """
    document = await tz_repository.get(doc_id)
    if document is None:
        raise HTTPException(status_code=404, detail="ТЗ не найдено")
    analysis = procurement_service.top_contractors_for_tz(document, top=top)
    return ContractorAnalysisResponse(**analysis)


@router.post("/{doc_id}/switch-template", response_model=TZDocumentResponse)
async def switch_document_template(doc_id: str, payload: TZSwitchTemplateRequest) -> TZDocumentResponse:
    document = await tz_repository.get(doc_id)
    if document is None:
        raise HTTPException(status_code=404, detail="ТЗ не найдено")
    template = tz_template_service.get_template(payload.template_key)
    if template is None:
        raise HTTPException(status_code=404, detail="Шаблон не найден")

    previous = {section.key: section for section in document.sections}
    template_keys = {section.key for section in template.sections}
    custom_sections = [section for section in document.sections if section.key.startswith("custom-") and section.key not in template_keys]
    document.sections = [
        previous.get(section.key) or TZDocumentSection(
            key=section.key, title=section.title, content="", source="template"
        )
        for section in template.sections
    ] + custom_sections
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
        "tz": document.model_dump(mode="json"),
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
    context = await enrich_assistant_context(
        payload.message, _chat_context(document, validation, payload.context)
    )
    reply, provider, fallback = assistant_service.generate(
        message=payload.message,
        context=context,
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
        discovery=context.get("discovery"),
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
