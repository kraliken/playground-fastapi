from dotenv import load_dotenv

load_dotenv()

from azure.identity import ClientSecretCredential
from azure.storage.blob import BlobServiceClient, BlobClient
import os

tenant_id = os.getenv("AZURE_TENANT_ID")
client_id = os.getenv("AZURE_CLIENT_ID")
client_secret = os.getenv("AZURE_CLIENT_SECRET")
account_url = os.getenv("AZURE_STORAGE_ACCOUNT_URL")
container_name = os.getenv("AZURE_STORAGE_CONTAINER_NAME", "invoices")

credential = ClientSecretCredential(
    tenant_id=tenant_id,
    client_id=client_id,
    client_secret=client_secret,
)
blob_service_client = BlobServiceClient(account_url=account_url, credential=credential)
container_client = blob_service_client.get_container_client(container_name)


def upload_pdf_to_blob(file_bytes: bytes, filename: str):
    blob_client = container_client.get_blob_client(filename)
    blob_client.upload_blob(file_bytes, overwrite=True)
    # Blob URL visszaadása
    return blob_client.url


def download_pdf_from_blob(blob_url):
    blob_name = blob_url.split("/")[-1]
    blob_client = container_client.get_blob_client(blob_name)
    stream = blob_client.download_blob()
    return stream.readall()


def delete_blob_from_url(blob_url: str):
    blob_name = blob_url.split("/")[-1]
    blob_client = container_client.get_blob_client(blob_name)
    blob_client.delete_blob()


def test_blob_connection():

    print("tenant_id:", tenant_id)
    print("client_id:", client_id)
    print("client_id:", client_secret)
    print("account_url:", account_url)

    try:
        print("Azure Blob Storage Python quickstart sample")

        credential = ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
        )
        blob_service_client = BlobServiceClient(
            account_url=account_url, credential=credential
        )

        # TESZT: Konténerek listázása (ha nincs jogosultság vagy gond, hibát kapsz)
        print("Elérhető blob konténerek:")
        container_list = blob_service_client.list_containers()
        for container in container_list:
            print(" -", container["name"])

        print("Kapcsolat sikeres!")

    except Exception as ex:
        print("Exception:")
        print(ex)


if __name__ == "__main__":
    test_blob_connection()
