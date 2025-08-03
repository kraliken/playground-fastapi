import base64
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from fastapi.responses import StreamingResponse

from database.models import PlayerRead
from routers.auth.oauth2 import get_current_user
from services.invoice_processor import (
    process_multialarm,
    process_volvo,
)
from utils.excel_export import (
    export_multialarm_to_excel_bytes,
    export_volvo_to_excel_bytes,
)


router = APIRouter(prefix="/nijhof", tags=["nijhof"])

OWN_TAX_ID = "25892941-2-41"


@router.post("/upload/invoice/volvo")
async def upload_volvo(
    file: UploadFile = File(...), current_user: PlayerRead = Depends(get_current_user)
):

    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Csak PDF fájl feltöltése engedélyezett.",
        )

    pdf_bytes = await file.read()

    try:
        data = process_volvo(pdf_bytes)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Nem sikerült a PDF-et feldolgozni: {str(e)}",
        )

    try:
        excel_bytes = export_volvo_to_excel_bytes(data)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Nem sikerült az Excel fájlt létrehozni: {str(e)}",
        )

    invoice_number = (
        data[0]["invoice_number"]
        if data and "invoice_number" in data[0]
        else "unknown_invoice_number"
    )

    return StreamingResponse(
        excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="volvo_invoice_{invoice_number}.xlsx"'
        },
    )


@router.post("/upload/invoice/multialarm")
async def upload_multialarm(file: UploadFile = File(...)):

    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Csak PDF fájl feltöltése engedélyezett.",
        )

    pdf_bytes = await file.read()

    try:
        data = process_multialarm(pdf_bytes)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Nem sikerült a PDF-et feldolgozni: {str(e)}",
        )

    if not data:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Nem található feldolgozható adat a PDF-ben.",
        )

    try:
        excel_bytes = export_multialarm_to_excel_bytes(data)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Nem sikerült az Excel fájlt létrehozni: {str(e)}",
        )

    if excel_bytes is None or (
        hasattr(excel_bytes, "getbuffer") and excel_bytes.getbuffer().nbytes == 0
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Nem sikerült Excel fájlt generálni a feldolgozott adatokból.",
        )
    invoice_number = (
        data[0]["invoice_number"]
        if data and "invoice_number" in data[0]
        else "unknown_invoice_number"
    )

    return StreamingResponse(
        excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="multialarm_invoice_{invoice_number}.xlsx"'
        },
    )
