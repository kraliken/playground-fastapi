from typing import List, Optional
from fastapi import APIRouter, Depends
from sqlmodel import func, select

from database.connection import SessionDep
from database.models import (
    CurrencyEnum,
    InvoiceStatusSummary,
    MonthlySummary,
    PlayerRead,
    StatusPieChartRow,
)
from routers.auth.oauth2 import get_current_user

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/income-expense-summary", response_model=List[MonthlySummary])
def get_monthly_income_expense(
    session: SessionDep, current_user: PlayerRead = Depends(get_current_user)
):

    results = session.exec(
        select(MonthlySummary).order_by(MonthlySummary.year, MonthlySummary.month)
    ).all()
    return results


@router.get("/invoice-status-summary", response_model=List[StatusPieChartRow])
def get_invoice_status_summary(
    session: SessionDep,
    current_user: PlayerRead = Depends(get_current_user),
    partner_name: Optional[str] = None,
):

    query = select(
        InvoiceStatusSummary.status,
        func.sum(InvoiceStatusSummary.total_amount).label("total_amount"),
    )

    if partner_name:
        query = query.where(InvoiceStatusSummary.partner_name == partner_name)

    query = query.group_by(InvoiceStatusSummary.status)

    results = session.exec(query).all()
    # Eredmény: [(status, total_amount), ...]
    # Átalakítjuk dict listává:
    return [{"status": row[0], "total_amount": row[1]} for row in results]


@router.get("/partners", response_model=List[str])
def get_partners(
    session: SessionDep, current_user: PlayerRead = Depends(get_current_user)
):
    # Egyedi partner nevek lekérése, ABC sorrendben
    partners = session.exec(
        select(InvoiceStatusSummary.partner_name)
        .distinct()
        .order_by(InvoiceStatusSummary.partner_name)
    ).all()
    # Visszaadjuk sima string listaként
    return partners
