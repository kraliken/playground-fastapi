from sqlmodel import Session, select
from database.models import Partner

def get_partner_by_tax_number(session: Session, tax_number: str):
    statement = select(Partner).where(Partner.tax_number == tax_number)
    result = session.exec(statement)
    return result.first()