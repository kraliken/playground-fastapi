from sqlmodel import SQLModel, Field, Relationship, Column, ForeignKey
from typing import List, Optional
from enum import Enum
from datetime import datetime


class EmailType(str, Enum):
    to = "to"
    cc = "cc"
    bcc = "bcc"


class Status(str, Enum):
    pending = "pending"
    ready = "ready"


class PartnerEmailLink(SQLModel, table=True):
    __tablename__ = "partner_email_link"

    partner_id: Optional[int] = Field(
        default=None, foreign_key="partners.id", primary_key=True
    )
    email_id: Optional[int] = Field(
        default=None, foreign_key="partner_emails.id", primary_key=True
    )

    partner: Optional["Partner"] = Relationship(back_populates="partner_links")
    email: Optional["PartnerEmail"] = Relationship(back_populates="email_links")


class Partner(SQLModel, table=True):
    __tablename__ = "partners"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=255, nullable=False)
    tax_number: str = Field(max_length=32, nullable=False)
    contact: Optional[str] = Field(default=None, max_length=255, nullable=True)

    emails: List["PartnerEmail"] = Relationship(
        back_populates="partners", link_model=PartnerEmailLink
    )
    partner_links: List["PartnerEmailLink"] = Relationship(back_populates="partner")
    invoices: List["UploadedInvoice"] = Relationship(back_populates="partner")


class PartnerCreate(SQLModel):
    name: str
    tax_number: str
    contact: Optional[str] = None


class PartnerEmail(SQLModel, table=True):
    __tablename__ = "partner_emails"

    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(max_length=255, nullable=False)
    type: EmailType = Field(nullable=False)

    partners: List[Partner] = Relationship(
        back_populates="emails", link_model=PartnerEmailLink
    )
    email_links: List["PartnerEmailLink"] = Relationship(back_populates="email")


class UploadedInvoice(SQLModel, table=True):
    __tablename__ = "uploaded_invoices"

    id: int | None = Field(default=None, primary_key=True)
    filename: str = Field(nullable=False)
    own_tax_id: str | None = Field(default=None)
    partner_tax_id: str | None = Field(default=None)
    partner_id: int | None = Field(default=None, foreign_key="partners.id")
    blob_url: str | None = Field(default=None)
    status: Status = Field(default=Status.pending, nullable=False)
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)

    partner: Optional["Partner"] = Relationship(back_populates="invoices")


class PartnerEmailResponse(SQLModel):
    id: int
    email: str
    type: EmailType


class PartnerEmailCreate(SQLModel):
    email: str
    type: EmailType
    # partner_ids: Optional[List[int]] = None


class PartnerEmailUpdate(SQLModel):
    email: Optional[str] = None
    type: Optional[EmailType] = None


class PartnerRead(SQLModel):
    id: int
    name: str
    tax_number: str
    contact: Optional[str] = None
    emails: List[PartnerEmailResponse] = []


class PartnerUpdate(SQLModel):
    name: Optional[str] = None
    tax_number: Optional[str] = None
    contact: Optional[str] = None


class Employee(SQLModel, table=True):

    id: int = Field(default=None, primary_key=True)
    name: str = Field(unique=True, max_length=50)
    axapta_name: Optional[str] = Field(default=None)
    monogram: str = Field(default=None)
    cost_center: str = Field(default=None)

    phone_numbers: List["PhoneBook"] = Relationship(back_populates="employee")


class PhoneBook(SQLModel, table=True):

    id: int = Field(default=None, primary_key=True)
    phone_number: str = Field(unique=True, max_length=12)

    employee_id: int = Field(foreign_key="employee.id")
    employee: Optional[Employee] = Relationship(back_populates="phone_numbers")


class VatCode(SQLModel, table=True):

    id: int = Field(default=None, primary_key=True)
    code: str = Field(unique=True, max_length=12)
    rate: Optional[str] = Field(default=None, max_length=4)

    mappings: List["TeszorVatExpenseMap"] = Relationship(back_populates="vat_code")


class TeszorCode(SQLModel, table=True):

    id: Optional[int] = Field(default=None, primary_key=True)
    teszor_code: str = Field(unique=True, max_length=20)

    mappings: List["TeszorVatExpenseMap"] = Relationship(back_populates="teszor_code")


class ExpenseType(SQLModel, table=True):

    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(unique=True, max_length=25)
    account_number: str = Field(max_length=10)

    mappings: List["TeszorVatExpenseMap"] = Relationship(back_populates="expense_type")


class TeszorVatExpenseMap(SQLModel, table=True):

    id: int = Field(default=None, primary_key=True)
    teszor_code_id: int = Field(foreign_key="teszorcode.id")
    vat_code_id: int = Field(foreign_key="vatcode.id")
    expense_type_id: int = Field(foreign_key="expensetype.id")

    teszor_code: Optional["TeszorCode"] = Relationship(back_populates="mappings")
    vat_code: Optional["VatCode"] = Relationship(back_populates="mappings")
    expense_type: Optional["ExpenseType"] = Relationship(back_populates="mappings")


class EmployeeRead(SQLModel):
    # id: int
    name: str
    axapta_name: Optional[str]
    monogram: Optional[str]
    cost_center: Optional[str]


class PhoneBookRead(SQLModel):
    id: int
    phone_number: str
    # employee_id: int
    employee: Optional[EmployeeRead]


class TeszorVatLedgerMapRead(SQLModel):
    # id: int
    # teszor_code_id: int
    # vat_code_id: int
    # expense_type_id: int
    teszor_code: Optional[str]
    vat_code: Optional[str]
    vat_rate: Optional[str]
    expense_title: Optional[str]
    expense_account_number: Optional[str]
