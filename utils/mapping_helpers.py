from sqlmodel import select
from sqlalchemy.orm import joinedload

from database.models import PhoneBook, TeszorVatExpenseMap, TeszorVatLedgerMapRead


def get_phone_user_map(session):

    statement = select(PhoneBook).options(joinedload(PhoneBook.employee))
    phonebooks = session.exec(statement).all()
    phone_user_map = {row.phone_number: row.employee.dict() for row in phonebooks}
    return phone_user_map


def get_teszor_mapping_lookup(session):
    statement = (
        select(TeszorVatExpenseMap)
        .join(TeszorVatExpenseMap.teszor_code)
        .join(TeszorVatExpenseMap.vat_code)
        .join(TeszorVatExpenseMap.expense_type)
    )
    mappings = session.exec(statement).all()
    teszor_mappings = []
    for m in mappings:
        teszor_mappings.append(
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

    teszor_category_map = {
        m.teszor_code: m.expense_title
        for m in teszor_mappings
        if m.teszor_code and m.expense_title
    }
    mapping_lookup = {
        (m.teszor_code, m.vat_rate): {
            "Title": m.expense_title,
            "VatCode": m.vat_code,
            "LedgerAccount": m.expense_account_number,
        }
        for m in teszor_mappings
        if m.teszor_code and m.vat_code and m.expense_title
    }

    return teszor_category_map, mapping_lookup
