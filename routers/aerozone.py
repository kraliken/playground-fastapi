import base64
from typing import List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status, Form
from sqlmodel import select, case
from sqlalchemy.orm import joinedload
from collections import defaultdict


from database.connection import SessionDep
from database.models import (
    Partner,
    PartnerCreate,
    PartnerEmail,
    PartnerEmailCreate,
    PartnerEmailLink,
    PartnerEmailResponse,
    PartnerEmailUpdate,
    PartnerRead,
    PartnerUpdate,
    PlayerRead,
    Status,
    UploadedInvoice,
)
from routers.auth.oauth2 import get_current_user
from services.blob_service import (
    delete_blob_from_url,
    download_pdf_from_blob,
    upload_pdf_to_blob,
)
from services.email_service import send_email_with_attachment
from services.invoice_processor import extract_tax_ids_from_pdf
from services.partner_service import get_partner_by_tax_number

router = APIRouter(prefix="/aerozone", tags=["aerozone"])

OWN_TAX_ID = "25892941-2-41"


@router.get("/invoices/all")
def get_uploaded_invoices(
    session: SessionDep, current_user: PlayerRead = Depends(get_current_user)
):
    statement = select(UploadedInvoice).options(
        joinedload(UploadedInvoice.partner).joinedload(Partner.emails)
    )
    invoices = session.exec(statement).unique().all()

    incomplete = []

    partner_invoice_map = defaultdict(lambda: {"partner_data": None, "invoices": []})

    for invoice in invoices:
        # Partner és annak emailcímei előkészítve frontendnek
        partner_data = None
        if invoice.partner:
            emails = [email.model_dump() for email in invoice.partner.emails]
            partner_data = invoice.partner.model_dump()
            partner_data["emails"] = emails

            to_emails = [email for email in emails if email["type"] == "to"]

            if to_emails:  # van partner ÉS van legalább 1 "to" típusú email
                partner_id = invoice.partner.id
                # Itt csak egyszer állítod be az emails-t (többszörös hozzáadás esetén sincs gond)
                if not partner_invoice_map[partner_id]["partner_data"]:
                    partner_invoice_map[partner_id]["partner_data"] = partner_data
                partner_invoice_map[partner_id]["invoices"].append(
                    {
                        "id": invoice.id,
                        "filename": invoice.filename,
                        "own_tax_id": invoice.own_tax_id,
                        "partner_tax_id": invoice.partner_tax_id,
                        "blob_url": invoice.blob_url,
                        "status": invoice.status,
                        "uploaded_at": invoice.uploaded_at,
                    }
                )
            else:  # van partner, de nincs emailcím
                incomplete.append(
                    {
                        "id": invoice.id,
                        "filename": invoice.filename,
                        "own_tax_id": invoice.own_tax_id,
                        "partner_tax_id": invoice.partner_tax_id,
                        "blob_url": invoice.blob_url,
                        "status": invoice.status,
                        "uploaded_at": invoice.uploaded_at,
                        "partner_data": partner_data,
                    }
                )
        else:  # nincs partner
            incomplete.append(
                {
                    "id": invoice.id,
                    "filename": invoice.filename,
                    "own_tax_id": invoice.own_tax_id,
                    "partner_tax_id": invoice.partner_tax_id,
                    "blob_url": invoice.blob_url,
                    "status": invoice.status,
                    "uploaded_at": invoice.uploaded_at,
                    "partner_data": None,
                }
            )

    complete_grouped = list(partner_invoice_map.values())
    return {
        "complete": complete_grouped,
        "incomplete": incomplete,
    }


@router.post("/upload/invoices")
async def upload_invoice(
    session: SessionDep,
    invoices: List[UploadFile] = File(...),
    current_user: PlayerRead = Depends(get_current_user),
):
    errors = []

    for file in invoices:

        blob_url = None

        if file.content_type != "application/pdf" or not file.filename.lower().endswith(
            ".pdf"
        ):
            errors.append(
                {"filename": file.filename, "error": "Csak PDF fájl tölthető fel!"}
            )
            continue

        try:

            file_bytes = await file.read()
            own_tax_id, partner_tax_id = extract_tax_ids_from_pdf(
                file_bytes, OWN_TAX_ID
            )

            partner = (
                get_partner_by_tax_number(session, partner_tax_id)
                if partner_tax_id
                else None
            )

            blob_url = upload_pdf_to_blob(file_bytes, file.filename)

            invoice_db = UploadedInvoice(
                filename=file.filename,
                own_tax_id=own_tax_id,
                partner_tax_id=partner_tax_id,
                partner_id=partner.id if partner else None,
                blob_url=blob_url,
                status=Status.pending,  # vagy dönthetsz: Status.ready, ha minden adat megvan!
            )

            session.add(invoice_db)
            session.commit()
            session.refresh(invoice_db)

        except Exception as e:
            errors.append({"filename": file.filename, "error": str(e)})

    if errors and len(errors) == len(invoices):
        return {
            "success": False,
            "message": "Egyik számlát sem sikerült elmenteni.",
            "errors": errors,
        }
    elif errors:
        return {
            "success": False,
            "message": "Néhány számlát nem sikerült elmenteni.",
            "errors": errors,
        }
    else:
        return {"success": True, "message": "Az összes számla sikeresen elmentve."}


@router.post("/invoices/send")
def send_complete_invoices(
    session: SessionDep,
    subject: str = Form(...),
    message: str = Form(...),
    current_user: PlayerRead = Depends(get_current_user),
):
    statement = select(UploadedInvoice).options(
        joinedload(UploadedInvoice.partner).joinedload(Partner.emails)
    )
    invoices = session.exec(statement).unique().all()

    partner_invoice_map = defaultdict(
        lambda: {"partner": None, "to_emails": [], "cc_emails": [], "invoices": []}
    )
    for invoice in invoices:
        partner = invoice.partner
        if not partner:
            continue

        to_emails = [e for e in partner.emails if e.type == "to"]
        cc_emails = [e for e in partner.emails if e.type == "cc"]
        if not to_emails:
            continue

        partner_id = partner.id
        if not partner_invoice_map[partner_id]["partner"]:
            partner_invoice_map[partner_id]["partner"] = partner
            partner_invoice_map[partner_id]["to_emails"] = to_emails
            partner_invoice_map[partner_id]["cc_emails"] = cc_emails
        partner_invoice_map[partner_id]["invoices"].append(invoice)

    sent = []
    failed = []

    for p in partner_invoice_map.values():
        to_email_addresses = [e.email for e in p["to_emails"]]
        cc_email_addresses = [e.email for e in p["cc_emails"]]
        partner_name = p["partner"].name
        attachments = []

        for invoice in p["invoices"]:
            try:
                print("BLOBOK LEKÉRDEZÉSE START")
                pdf_bytes = download_pdf_from_blob(invoice.blob_url)
            except Exception as e:
                failed.append(
                    {
                        "partner": partner_name,
                        "error": f"Nem sikerült a PDF-et letölteni: {invoice.filename} ({str(e)})",
                    }
                )
                continue

            attachments.append(
                {
                    "name": invoice.filename,
                    "contentType": "application/pdf",
                    "contentInBase64": base64.b64encode(pdf_bytes).decode(),
                }
            )
        if not attachments:
            failed.append(
                {"partner": partner_name, "error": "Nincs letölthető számla."}
            )
            continue

        try:

            html = f"<p>{message.replace('\r\n', '<br>').replace('\n', '<br>').replace('\r', '<br>')}</p>"

            send_email_with_attachment(
                to_emails=to_email_addresses,
                cc_emails=cc_email_addresses,
                subject=subject,
                html=html,
                plainText=message,
                attachments=attachments,
            )

            print("EMAIL KÜLDÉS HÍVÁS end")
            for invoice in p["invoices"]:
                delete_blob_from_url(invoice.blob_url)
                print("Blob törlés sikeres")

            for invoice in p["invoices"]:
                session.delete(invoice)

            session.commit()

            sent.append(
                {
                    "partner": partner_name,
                    "emails": to_email_addresses,
                    "invoices": [a["name"] for a in attachments],
                }
            )
        except Exception as e:
            session.rollback()
            failed.append(
                {"partner": partner_name, "error": f"E-mail küldési hiba: {str(e)}"}
            )
    return {
        "success": len(failed) == 0,
        "sent": sent,
        "failed": failed,
        "message": f"{len(sent)} email elküldve, {len(failed)} hibás.",
    }


@router.delete("/invoices/delete")
def delete_invoices(
    session: SessionDep, current_user: PlayerRead = Depends(get_current_user)
):
    invoices = session.exec(select(UploadedInvoice)).all()
    errors = []

    for invoice in invoices:
        try:
            if invoice.blob_url:
                delete_blob_from_url(invoice.blob_url)
        except Exception as e:
            errors.append({"filename": invoice.filename, "error": str(e)})

        session.delete(invoice)

    session.commit()

    if errors:
        return {
            "success": False,
            "message": f"{len(errors)} számla blob törlése sikertelen volt.",
            "errors": errors,
        }
    else:
        return {
            "success": True,
            "message": "Az összes számla és blob sikeresen törölve.",
        }


@router.post(
    "/partner/create", status_code=status.HTTP_201_CREATED, response_model=PartnerRead
)
def create_partner(
    partner: PartnerCreate,
    session: SessionDep,
    current_user: PlayerRead = Depends(get_current_user),
):

    db_partner = Partner(
        name=partner.name, tax_number=partner.tax_number, contact=partner.contact
    )
    session.add(db_partner)
    session.commit()
    session.refresh(db_partner)

    statement = select(UploadedInvoice).where(
        UploadedInvoice.partner_id == None,
        UploadedInvoice.partner_tax_id == db_partner.tax_number,
    )
    invoices_to_update = session.exec(statement).all()

    for inv in invoices_to_update:
        inv.partner_id = db_partner.id
    if invoices_to_update:
        session.commit()

    session.refresh(db_partner)
    return db_partner


@router.patch("/partner/{partner_id}", response_model=PartnerUpdate)
def update_partner(
    partner_id: int,
    partner_update: PartnerUpdate,
    session: SessionDep,
    current_user: PlayerRead = Depends(get_current_user),
):
    partner = session.get(Partner, partner_id)
    if not partner:
        raise HTTPException(status_code=404, detail="Partner not found")
    partner_data = partner_update.model_dump(exclude_unset=True)
    for key, value in partner_data.items():
        setattr(partner, key, value)

    session.add(partner)
    session.commit()
    session.refresh(partner)

    statement = select(UploadedInvoice).where(
        UploadedInvoice.partner_id == None,
        UploadedInvoice.partner_tax_id == partner.tax_number,
    )
    invoices_to_update = session.exec(statement).all()

    for inv in invoices_to_update:
        inv.partner_id = partner.id
    if invoices_to_update:
        session.commit()

    return partner


@router.delete("/partner/{partner_id}")
def delete_partner(
    partner_id: int,
    session: SessionDep,
    current_user: PlayerRead = Depends(get_current_user),
):

    statement = select(PartnerEmailLink).where(
        PartnerEmailLink.partner_id == partner_id
    )
    links = session.exec(statement).all()
    for link in links:
        session.delete(link)
    session.commit()

    partner = session.get(Partner, partner_id)
    if not partner:
        raise HTTPException(status_code=404, detail="Partner not found")
    session.delete(partner)
    session.commit()
    return {"success": "true"}


@router.get("/partners/all", response_model=List[PartnerRead])
def get_partners(
    session: SessionDep, current_user: PlayerRead = Depends(get_current_user)
):
    partners = session.exec(select(Partner)).all()

    return partners


@router.post(
    "/email/create",
    status_code=status.HTTP_201_CREATED,
    response_model=PartnerEmailResponse,
)
def create_partner_email(
    email_in: PartnerEmailCreate,
    session: SessionDep,
    current_user: PlayerRead = Depends(get_current_user),
):

    db_email = PartnerEmail(email=email_in.email, type=email_in.type)
    session.add(db_email)
    session.commit()
    session.refresh(db_email)

    return db_email


@router.patch("/email/{email_id}", response_model=PartnerEmailUpdate)
def update_email(
    email_id: int,
    email_update: PartnerEmailUpdate,
    session: SessionDep,
    current_user: PlayerRead = Depends(get_current_user),
):
    email = session.get(PartnerEmail, email_id)
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
    email_data = email_update.model_dump(exclude_unset=True)
    for key, value in email_data.items():
        setattr(email, key, value)

    session.add(email)
    session.commit()
    session.refresh(email)

    return email


@router.delete("/email/{email_id}")
def delete_partner(
    email_id: int,
    session: SessionDep,
    current_user: PlayerRead = Depends(get_current_user),
):

    statement = select(PartnerEmailLink).where(PartnerEmailLink.email_id == email_id)
    links = session.exec(statement).all()
    for link in links:
        session.delete(link)
    session.commit()

    email = session.get(PartnerEmail, email_id)
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
    session.delete(email)
    session.commit()
    return {"success": "true"}


@router.get("/emails/all", response_model=List[PartnerEmailResponse])
def get_emails(
    session: SessionDep, current_user: PlayerRead = Depends(get_current_user)
):

    emails = session.exec(select(PartnerEmail)).all()

    return emails


@router.get("/emails/available/{partner_id}", response_model=List[PartnerEmailResponse])
def get_available_to_emails(
    partner_id: int,
    type: str,
    session: SessionDep,
    current_user: PlayerRead = Depends(get_current_user),
):
    linked_email_ids = session.exec(
        select(PartnerEmailLink.email_id).where(
            PartnerEmailLink.partner_id == partner_id
        )
    ).all()

    statement = (
        select(PartnerEmail)
        .where(PartnerEmail.type == type)
        .where(PartnerEmail.id.notin_(linked_email_ids if linked_email_ids else [0]))
    )
    emails = session.exec(statement).all()

    return emails


@router.get("/connection/all")
def get_connections(
    session: SessionDep, current_user: PlayerRead = Depends(get_current_user)
):

    type_order = case((PartnerEmail.type == "to", 0), else_=1)

    statement = (
        select(PartnerEmailLink)
        .options(
            joinedload(PartnerEmailLink.partner), joinedload(PartnerEmailLink.email)
        )
        .join(Partner, PartnerEmailLink.partner_id == Partner.id)
        .join(PartnerEmail, PartnerEmailLink.email_id == PartnerEmail.id)
        .order_by(Partner.name, type_order)
    )

    links = session.exec(statement).all()
    result = []
    for link in links:
        partner = session.get(Partner, link.partner_id)
        email = session.get(PartnerEmail, link.email_id)
        result.append(
            {
                "partner_id": link.partner_id,
                "partner_name": partner.name if partner else None,
                "email_id": link.email_id,
                "email": email.email if email else None,
                "type": email.type if email else None,
            }
        )
    return result


@router.post("/connection/create")
def link_email_to_partner(
    email_id: int,
    partner_id: int,
    session: SessionDep,
    current_user: PlayerRead = Depends(get_current_user),
):

    link = PartnerEmailLink(partner_id=partner_id, email_id=email_id)
    session.add(link)
    session.commit()

    return {"message": "Email összekapcsolva a partnerrel."}


@router.delete("/connection/delete")
def delete_connection(
    email_id: int,
    partner_id: int,
    session: SessionDep,
    current_user: PlayerRead = Depends(get_current_user),
):
    statement = select(PartnerEmailLink).where(
        PartnerEmailLink.partner_id == partner_id,
        PartnerEmailLink.email_id == email_id,
    )
    link = session.exec(statement).first()
    if not link:
        return {"success": False, "message": "Kapcsolat nem található."}
    session.delete(link)
    session.commit()
    return {"success": True, "message": "Kapcsolat törölve."}
