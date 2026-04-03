"""Human-in-the-loop PO approval endpoint."""

from pydantic import BaseModel
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app import approval_signal
from app.events import event_store
from app.messages import message_store
from app.state import store
from app.tools.tool_functions import approve_purchase_order

router = APIRouter(tags=["approval"])


class ApprovalRequest(BaseModel):
    approved: bool
    note: str = ""


@router.post("/approval/{po_id}")
async def human_approve(po_id: str, body: ApprovalRequest):
    """Accept or reject a PO that is pending human approval."""
    result = await approve_purchase_order(
        po_id,
        approved=body.approved,
        note=body.note or (
            "Human approved via UI" if body.approved else "Human rejected via UI"),
        state_store=store,
        event_store=event_store,
        message_store=message_store,
    )
    if not result.get("ok"):
        return JSONResponse(status_code=400, content=result)
    # Wake the orchestrator polling loop
    approval_signal.signal()
    return result
