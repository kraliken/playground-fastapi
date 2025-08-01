import base64
from fastapi import APIRouter, Form, UploadFile, File, HTTPException, status
from fastapi.responses import StreamingResponse

from database.connection import SessionDep
from services.email_service import send_email_with_attachment
from services.invoice_processor import (
    process_multialarm,
    process_vodafone,
    process_volvo,
)
from utils.excel_export import (
    export_multialarm_to_excel_bytes,
    export_vodafone_to_excel_bytes,
    export_volvo_to_excel_bytes,
)
from utils.mapping_helpers import get_phone_user_map, get_teszor_mapping_lookup


router = APIRouter(prefix="/upload", tags=["upload"])

OWN_TAX_ID = "25892941-2-41"


@router.post("/invoice/volvo")
async def upload_volvo(file: UploadFile = File(...)):

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


@router.post("/invoice/multialarm")
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


@router.post("/invoice/vodafone")
async def upload_vodafone(session: SessionDep, file: UploadFile = File(...)):

    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Csak PDF fájl feltöltése engedélyezett.",
        )

    pdf_bytes = await file.read()
    result = process_vodafone(pdf_bytes)

    if not result["invoice_summary"] and not result["service_charges"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Csak olyan PDF fájl tölthető fel, amely releváns számlaadatokat tartalmaz.",
        )

    try:
        phone_user_map = get_phone_user_map(session)
        teszor_category_map, mapping_lookup = get_teszor_mapping_lookup(session)
        excel_buffer = export_vodafone_to_excel_bytes(
            result, phone_user_map, teszor_category_map, mapping_lookup
        )

        filename = (
            f"vodafone_{result["invoice_number"]}.xlsx"
            if result["invoice_number"]
            else "vodafone_invoice_data.xlsx"
        )
        return StreamingResponse(
            excel_buffer,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Váratlan hiba történt: {e}",
        )


@router.post("/send/vodafone")
async def upload_vodafone(
    session: SessionDep,
    recipient: str = Form(...),
    subject: str = Form(...),
    message: str = Form(...),
    attachment: UploadFile = File(...),
):

    html = f"<p>{message.replace('\r\n', '<br>').replace('\n', '<br>').replace('\r', '<br>')}</p>"

    if attachment.content_type != "application/pdf":
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Csak PDF fájl feltöltése engedélyezett.",
        )

    pdf_bytes = await attachment.read()
    result = process_vodafone(pdf_bytes)

    if not result["invoice_summary"] and not result["service_charges"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Csak olyan PDF fájl tölthető fel, amely releváns számlaadatokat tartalmaz.",
        )

    try:
        phone_user_map = get_phone_user_map(session)
        teszor_category_map, mapping_lookup = get_teszor_mapping_lookup(session)
        excel_buffer = export_vodafone_to_excel_bytes(
            result, phone_user_map, teszor_category_map, mapping_lookup
        )

        filename = (
            f"vodafone_{result["invoice_number"]}.xlsx"
            if result["invoice_number"]
            else "vodafone_invoice_data.xlsx"
        )
        attachments = [
            {
                "name": attachment.filename,
                "contentType": "application/pdf",
                "contentInBase64": base64.b64encode(pdf_bytes).decode(),
            },
            {
                "name": filename,
                "contentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "contentInBase64": base64.b64encode(excel_buffer.getvalue()).decode(),
            },
        ]
        result = send_email_with_attachment(
            to_emails=recipient,
            cc_emails="kraaliknorbert@gmail.com",
            subject=subject,
            html=html,
            plainText=message,
            attachments=attachments,
        )

        return result

        # message = {
        #     "senderAddress": "DoNotReply@playground.kraliknorbert.com",
        #     "recipients": {
        #         "to": [{"address": recipient}],
        #         "cc": [{"address": "kraaliknorbert@gmail.com"}],
        #     },
        #     "content": {
        #         "subject": subject,
        #         "plainText": message,
        #         "html": html,
        #     },
        #     "attachments": attachments,
        # }
        # return StreamingResponse(
        #     excel_buffer,
        #     media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        #     headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        # )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Váratlan hiba történt: {e}",
        )
