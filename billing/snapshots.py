"""Frozen copies of everything a document must keep saying after it is issued.

A document reads its identity through ``Document.snapshot``, which returns one
of these whether the document is a draft (built live from current settings) or
issued (rebuilt from the stored JSON). One code path for both, and access is
attribute-based -- ``snapshot.bank.account_number`` -- so a typo raises at
render time instead of printing a blank line on a client's invoice.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from decimal import Decimal

from core.phone import format_za

from .money import to_decimal

# Bumped if the stored shape ever changes incompatibly. Readers branch on it;
# writers always emit the current version.
SNAPSHOT_VERSION = 1


@dataclass(frozen=True)
class BusinessSnapshot:
    name: str = ""
    address: str = ""
    phone: str = ""
    email: str = ""

    @property
    def phone_display(self) -> str:
        return format_za(self.phone)

    @property
    def address_lines(self) -> list[str]:
        return [line.strip() for line in self.address.splitlines() if line.strip()]


@dataclass(frozen=True)
class BankSnapshot:
    bank_name: str = ""
    branch_name: str = ""
    branch_code: str = ""
    account_holder: str = ""
    account_number: str = ""
    account_type: str = ""
    swift_code: str = ""

    # Order matters: this is the order it prints in.
    LABELS = (
        ("account_holder", "Account holder"),
        ("bank_name", "Bank"),
        ("account_number", "Account no."),
        ("account_type", "Type"),
        ("branch_name", "Branch"),
        ("branch_code", "Branch code"),
        ("swift_code", "SWIFT"),
    )

    @property
    def rows(self) -> list[tuple[str, str]]:
        """Label/value pairs with empty fields dropped -- fault 2, fault 4."""
        return [
            (label, getattr(self, name))
            for name, label in self.LABELS
            if (getattr(self, name) or "").strip()
        ]

    @property
    def is_complete(self) -> bool:
        return bool(self.account_number and self.bank_name)


@dataclass(frozen=True)
class ClientSnapshot:
    company: str = ""
    contact_person: str = ""
    email: str = ""
    phone: str = ""
    address: str = ""

    @property
    def phone_display(self) -> str:
        return format_za(self.phone)

    @property
    def address_lines(self) -> list[str]:
        return [line.strip() for line in self.address.splitlines() if line.strip()]


@dataclass(frozen=True)
class DocumentSnapshot:
    business: BusinessSnapshot = field(default_factory=BusinessSnapshot)
    bank: BankSnapshot = field(default_factory=BankSnapshot)
    client: ClientSnapshot = field(default_factory=ClientSnapshot)
    vat_registered: bool = False
    vat_number: str = ""
    vat_rate: Decimal = Decimal("0")
    accent_colour: str = "#8A3324"

    def to_dict(self) -> dict:
        data = asdict(self)
        data["vat_rate"] = str(self.vat_rate)
        data["version"] = SNAPSHOT_VERSION
        return data

    @classmethod
    def from_dict(cls, data: dict | None) -> "DocumentSnapshot":
        data = data or {}
        return cls(
            business=BusinessSnapshot(**_only_fields(BusinessSnapshot, data.get("business"))),
            bank=BankSnapshot(**_only_fields(BankSnapshot, data.get("bank"))),
            client=ClientSnapshot(**_only_fields(ClientSnapshot, data.get("client"))),
            vat_registered=bool(data.get("vat_registered", False)),
            vat_number=data.get("vat_number", ""),
            vat_rate=to_decimal(data.get("vat_rate", 0)),
            accent_colour=data.get("accent_colour") or "#8A3324",
        )


def _only_fields(cls, data: dict | None) -> dict:
    """Drop unknown keys so a snapshot written by an older version still loads."""
    allowed = set(cls.__dataclass_fields__)
    return {k: v for k, v in (data or {}).items() if k in allowed}
