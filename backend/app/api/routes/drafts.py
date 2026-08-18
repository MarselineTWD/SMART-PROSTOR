from fastapi import APIRouter
from fastapi.responses import FileResponse

from backend.app.schemas.draft import DraftEvaluationRequest, DraftFromSearchRequest, DraftResponse
from backend.app.services.documents import document_export_service
from backend.app.services.drafts import draft_service
from backend.app.services.rules import rules_service


router = APIRouter()


@router.post("/from-search", response_model=DraftResponse)
def create_from_search(payload: DraftFromSearchRequest) -> DraftResponse:
    draft = draft_service.create_from_search(payload)
    return DraftResponse(draft=draft)


@router.post("/evaluate", response_model=DraftResponse)
def evaluate_draft(payload: DraftEvaluationRequest) -> DraftResponse:
    draft = rules_service.evaluate(payload.draft)
    return DraftResponse(draft=draft)


@router.post("/export")
def export_draft(payload: DraftEvaluationRequest) -> FileResponse:
    docx_path = document_export_service.export_from_draft(payload.draft)
    return FileResponse(
        path=docx_path,
        filename=docx_path.name,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
