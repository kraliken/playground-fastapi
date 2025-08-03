from typing import List
import base64
from fastapi import APIRouter, Depends, Form, UploadFile, File, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlmodel import select
from sqlalchemy.orm import joinedload

from database.connection import SessionDep
from database.models import (
    PhoneBook,
    PhoneBookRead,
    PlayerRead,
    TeszorVatExpenseMap,
    TeszorVatLedgerMapRead,
)
from routers.auth.oauth2 import get_current_user
from services.email_service import send_email_with_attachment
from services.invoice_processor import process_vodafone
from utils.excel_export import export_vodafone_to_excel_bytes
from utils.mapping_helpers import get_phone_user_map, get_teszor_mapping_lookup

router = APIRouter(prefix="/esselte", tags=["esselte"])


@router.get("/phonebook", response_model=List[PhoneBookRead])
def get_phonebook(
    session: SessionDep, current_user: PlayerRead = Depends(get_current_user)
):

    statement = select(PhoneBook).options(joinedload(PhoneBook.employee))
    phonebooks = session.exec(statement).all()
    return phonebooks


@router.get("/teszor-mapping", response_model=List[TeszorVatLedgerMapRead])
def get_teszor_mappings(
    session: SessionDep, current_user: PlayerRead = Depends(get_current_user)
):

    statement = (
        select(TeszorVatExpenseMap)
        .join(TeszorVatExpenseMap.teszor_code)
        .join(TeszorVatExpenseMap.vat_code)
        .join(TeszorVatExpenseMap.expense_type)
    )
    mappings = session.exec(statement).all()
    result = []
    for m in mappings:
        result.append(
            TeszorVatLedgerMapRead(
                teszor_code=m.teszor_code.teszor_code if m.teszor_code else None,
                vat_code=m.vat_code.code if m.vat_code else None,
                vat_rate=m.vat_code.rate if m.vat_code else None,
                expense_title=m.expense_type.title if m.expense_type else None,
                expense_account_number=(
                    m.expense_type.account_number if m.expense_type else None
                ),
            )
        )
    return result


@router.post("/upload/invoice/vodafone")
async def upload_vodafone(
    session: SessionDep,
    file: UploadFile = File(...),
    current_user: PlayerRead = Depends(get_current_user),
):

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
    current_user: PlayerRead = Depends(get_current_user),
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
        to_list = [recipient]
        result = send_email_with_attachment(
            to_emails=to_list,
            cc_emails=["kraaliknorbert@gmail.com"],
            subject=subject,
            html=html,
            plainText=message,
            attachments=attachments,
        )

        return result

    except Exception as e:
        print("ez küldöm vissza")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Váratlan hiba történt: {e}",
        )
