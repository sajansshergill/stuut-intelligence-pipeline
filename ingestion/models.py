# ingestion/models.py

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Optional


VALID_STATUSES = {"OPEN", "PARTIAL", "PAID", "OVERDUE", "DISPUTED"}
VALID_SOURCES = {"netsuite", "quickbooks", "sap"}
VALID_PAYMENT_METHODS = {"ach", "wire", "credit_card", "check", "unknown"}
VALID_PAYMENT_PROCESSORS = {"stripe", "plaid", "manual", "bank"}
VALID_PRODUCT_EVENT_TYPES = {
    "email_sent",
    "call_logged",
    "reminder_triggered",
    "dispute_opened",
}
VALID_PRODUCT_OUTCOMES = {
    "delivered",
    "bounced",
    "connected",
    "voicemail",
    "resolved",
    "opened",
}


@dataclass
class InvoiceRecord:
    """
    Canonical invoice shape. Every ERP source normalizes into this
    before touching the warehouse - type errors caught here, not in dbt.
    """
    invoice_id: str
    customer_id: str
    invoice_date: date
    due_date: date
    amount_usd: Decimal
    currency: str
    status: str  # OPEN | PARTIAL | PAID | OVERDUE | DISPUTED
    source_system: str  # netsuite | quickbooks | sap

    # Optional enrichment fields
    customer_name: Optional[str] = None
    line_items: Optional[int] = None  # number of line items on invoice
    po_number: Optional[str] = None  # purchase order reference

    # Pipeline metadata - set automatically, never by caller
    _loaded_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    _source_file: str = ""

    def __post_init__(self):
        if isinstance(self.amount_usd, (int, float, str)):
            self.amount_usd = Decimal(str(self.amount_usd))
        if isinstance(self.invoice_date, str):
            self.invoice_date = date.fromisoformat(self.invoice_date)
        if isinstance(self.due_date, str):
            self.due_date = date.fromisoformat(self.due_date)
        self.currency = self.currency.upper()
        self.status = self.status.upper()
        self.source_system = self.source_system.lower()

        if self.status not in VALID_STATUSES:
            raise ValueError(f"Invalid status '{self.status}'. Must be one of {VALID_STATUSES}")
        if self.source_system not in VALID_SOURCES:
            raise ValueError(f"Invalid source_system '{self.source_system}'. Must be one of {VALID_SOURCES}")
        if self.amount_usd < 0:
            raise ValueError(f"amount_usd cannot be negative: {self.amount_usd}")
        if self.due_date < self.invoice_date:
            raise ValueError(f"due_date {self.due_date} is before invoice_date {self.invoice_date}")
        if self.line_items is not None and self.line_items < 0:
            raise ValueError(f"line_items cannot be negative: {self.line_items}")

    @property
    def days_outstanding(self) -> int:
        return self.days_outstanding_as_of(date.today())

    def days_outstanding_as_of(self, as_of_date: date) -> int:
        return (as_of_date - self.invoice_date).days

    @property
    def is_overdue(self) -> bool:
        return self.is_overdue_as_of(date.today())

    def is_overdue_as_of(self, as_of_date: date) -> bool:
        return as_of_date > self.due_date and self.status != "PAID"

    @property
    def aging_bucket(self) -> str:
        return self.aging_bucket_as_of(date.today())

    def aging_bucket_as_of(self, as_of_date: date) -> str:
        d = self.days_outstanding_as_of(as_of_date)
        if d <= 30:   return "0-30"
        if d <= 60:   return "31-60"
        if d <= 90:   return "61-90"
        return "90+"

    def to_dict(self) -> dict:
        return {
            "invoice_id": self.invoice_id,
            "customer_id": self.customer_id,
            "customer_name": self.customer_name,
            "invoice_date": self.invoice_date.isoformat(),
            "due_date": self.due_date.isoformat(),
            "amount_usd": float(self.amount_usd),
            "currency": self.currency,
            "status": self.status,
            "source_system": self.source_system,
            "po_number": self.po_number,
            "line_items": self.line_items,
            "days_outstanding": self.days_outstanding,
            "is_overdue": self.is_overdue,
            "aging_bucket": self.aging_bucket,
            "_loaded_at": self._loaded_at.isoformat(),
            "_source_file": self._source_file,
        }


@dataclass
class PaymentEvent:
    """
    Canonical payment shape. Stripe, ACH, wire, and check payments
    all normalize into this before warehouse load.
    """
    payment_id: str
    invoice_id: str  # FK to InvoiceRecord
    customer_id: str
    payment_date: date
    amount_usd: Decimal
    currency: str
    payment_method: str  # ach | wire | credit_card | check | unknown
    processor: str  # stripe | plaid | manual | bank
    is_partial: bool = False  # True if amount < invoice total

    # Optional
    reference_number: Optional[str] = None  # check number, wire ref, etc.
    notes: Optional[str] = None

    # Pipeline metadata
    _loaded_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    _source_event: str = ""  # raw webhook event ID

    def __post_init__(self):
        if isinstance(self.amount_usd, (int, float, str)):
            self.amount_usd = Decimal(str(self.amount_usd))
        if isinstance(self.payment_date, str):
            self.payment_date = date.fromisoformat(self.payment_date)
        self.currency = self.currency.upper()
        self.payment_method = self.payment_method.lower()
        self.processor = self.processor.lower()
        if self.payment_method not in VALID_PAYMENT_METHODS:
            raise ValueError(f"Invalid payment_method '{self.payment_method}'")
        if self.processor not in VALID_PAYMENT_PROCESSORS:
            raise ValueError(f"Invalid processor '{self.processor}'")
        if self.amount_usd <= 0:
            raise ValueError(f"Payment amount must be positive: {self.amount_usd}")

    def to_dict(self) -> dict:
        return {
            "payment_id": self.payment_id,
            "invoice_id": self.invoice_id,
            "customer_id": self.customer_id,
            "payment_date": self.payment_date.isoformat(),
            "amount_usd": float(self.amount_usd),
            "currency": self.currency,
            "payment_method": self.payment_method,
            "processor": self.processor,
            "is_partial": self.is_partial,
            "reference_number": self.reference_number,
            "notes": self.notes,
            "_loaded_at": self._loaded_at.isoformat(),
            "_source_event": self._source_event,
        }


@dataclass
class ProductEvent:
    """
    Canonical product event shape. Captures every collection
    touchpoint from the Stuut product — emails sent, calls logged,
    disputes opened, reminders triggered.
    """
    event_id: str
    invoice_id: str
    customer_id: str
    event_type: str  # email_sent | call_logged | reminder_triggered | dispute_opened
    occurred_at: datetime
    actor: str  # system | agent_id
    outcome: Optional[str] = None  # delivered | bounced | connected | voicemail | None

    _loaded_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    _source_event: str = ""

    def __post_init__(self):
        if isinstance(self.occurred_at, str):
            self.occurred_at = datetime.fromisoformat(self.occurred_at)
        self.event_type = self.event_type.lower()
        if self.outcome is not None:
            self.outcome = self.outcome.lower()
        if self.event_type not in VALID_PRODUCT_EVENT_TYPES:
            raise ValueError(f"Invalid event_type '{self.event_type}'")
        if self.outcome is not None and self.outcome not in VALID_PRODUCT_OUTCOMES:
            raise ValueError(f"Invalid outcome '{self.outcome}'")

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "invoice_id": self.invoice_id,
            "customer_id": self.customer_id,
            "event_type": self.event_type,
            "occurred_at": self.occurred_at.isoformat(),
            "actor": self.actor,
            "outcome": self.outcome,
            "_loaded_at": self._loaded_at.isoformat(),
            "_source_event": self._source_event,
        }