from typing import List
from fastapi import APIRouter
from sqlmodel import select
from sqlalchemy.orm import joinedload

from database.connection import SessionDep
from database.models import (
    PhoneBook,
    PhoneBookRead,
    TeszorVatExpenseMap,
    TeszorVatLedgerMapRead,
)

router = APIRouter(prefix="/esselte", tags=["esselte"])


@router.get("/phonebook", response_model=List[PhoneBookRead])
def get_phonebook(session: SessionDep):

    statement = select(PhoneBook).options(joinedload(PhoneBook.employee))
    phonebooks = session.exec(statement).all()
    return phonebooks


@router.get("/teszor-mapping", response_model=List[TeszorVatLedgerMapRead])
def get_teszor_mappings(session: SessionDep):

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
