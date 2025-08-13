from fastapi import APIRouter
import os
import msal
import requests
from sqlmodel import select

from database.connection import SessionDep
from database.models import Employee

router = APIRouter(prefix="/employees", tags=["employees"])

TENANT_ID = os.getenv("NEW_AZURE_TENANT_ID", "ide_tenant_id")
CLIENT_ID = os.getenv("NEW_AZURE_CLIENT_ID", "ide_client_id")
CLIENT_SECRET = os.getenv("NEW_AZURE_CLIENT_SECRET", "ide_client_secret")


def get_access_token():
    if not (TENANT_ID and CLIENT_ID and CLIENT_SECRET):
        raise RuntimeError(
            "Hiányzik valamelyik env: AZURE_TENANT_ID / AZURE_CLIENT_ID / AZURE_CLIENT_SECRET"
        )

    app = msal.ConfidentialClientApplication(
        CLIENT_ID,
        authority=f"https://login.microsoftonline.com/{TENANT_ID}",
        client_credential=CLIENT_SECRET,
    )
    result = app.acquire_token_for_client(
        scopes=["https://graph.microsoft.com/.default"]
    )
    if "access_token" not in result:
        # Részletes MSAL hiba
        raise RuntimeError(f"MSAL error: {result}")
    return result["access_token"]


@router.get("/all")
def get_all_employees(session: SessionDep):
    employees = session.exec(select(Employee)).all()
    return employees


# @router.get("/own")
# def list_users():
#     token = get_access_token()
#     headers = {"Authorization": f"Bearer {token}"}
#     graph_url = "https://graph.microsoft.com/v1.0/users"
#     r = requests.get(graph_url, headers=headers)
#     r.raise_for_status()
#     return r.json()
