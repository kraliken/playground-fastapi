from azure.communication.email import EmailClient
from fastapi import HTTPException
import os

connection_string = os.getenv("AZURE_EMAIL_CONNECTION_STRING")

email_client = EmailClient.from_connection_string(connection_string)


def send_email_with_attachment(
    to_emails, cc_emails, subject, html, plainText, attachments
):

    to_list = [{"address": email} for email in to_emails] if to_emails else []
    cc_list = [{"address": email} for email in cc_emails] if cc_emails else []

    message = {
        "senderAddress": "DoNotReply@playground.kraliknorbert.com",
        "recipients": {
            "to": to_list,
            "cc": cc_list,
        },
        "content": {
            "subject": subject,
            "plainText": plainText,
            "html": html,
        },
        "attachments": attachments,
    }

    try:
        poller = email_client.begin_send(message)
        result = poller.result()
        if result.get("status") == "Succeeded":
            print("Email sikeresen elküldve.")
            return {
                "message": "Email elküldve",
                "operation_id": result.get("id"),
                "status": result.get("status"),
            }
        else:
            print(
                f"Email küldés sikertelen! Status: {getattr(result, 'status', None)}, error: {getattr(result, 'error', None)}"
            )
            raise HTTPException(
                status_code=500,
                detail=f"Email küldés sikertelen! Status: {getattr(result, 'status', None)}, error: {getattr(result, 'error', None)}",
            )

    except Exception as ex:
        print(f"Email küldési hiba (kivétel): {ex}")
        raise HTTPException(status_code=500, detail=f"Email küldési hiba: {ex}")
