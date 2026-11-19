"""Fictional names, products, and market data used by the generator.

Every company, person, product, and number produced from this module is
synthetic. Names are assembled from syllables so they do not refer to real
organizations.
"""

from __future__ import annotations

import random

_SYL_A = ["cor", "val", "mir", "ast", "bel", "dar", "ken", "lum", "nor", "ost", "pal", "ryn", "sel", "tav", "ver", "zan", "kai", "mar", "tor", "elo"]
_SYL_B = ["ana", "ex", "ora", "ion", "ium", "eta", "ova", "is", "en", "ara", "ix", "um", "aro", "ella", "on"]
_INDUSTRY = ["Logistics", "Foods", "Textiles", "Systems", "Trading", "Components", "Packaging", "Analytics", "Machinery", "Media", "Pharma", "Agro", "Energy", "Retail"]

LEGAL_SUFFIX = {
    "Europe/Berlin": "GmbH",
    "Europe/London": "Ltd",
    "Asia/Almaty": "LLP",
    "Asia/Tokyo": "KK",
    "Asia/Kolkata": "Pvt Ltd",
    "Asia/Kathmandu": "Pvt Ltd",
    "America/New_York": "Inc",
    "America/Sao_Paulo": "Ltda",
    "Australia/Sydney": "Pty Ltd",
    "UTC": "Holdings",
}

# Sales catalogue: (description, unit price range in USD, quantity range)
SALES_ITEMS = [
    ("Pallet storage, per pallet-week", (4, 18), (10, 120)),
    ("Route planning licence, monthly", (90, 400), (1, 5)),
    ("Cold-chain transport, per trip", (220, 1400), (1, 8)),
    ("Packaging film 500 m roll", (12, 45), (5, 60)),
    ("Calibration service visit", (150, 700), (1, 4)),
    ("Custom label print run", (40, 260), (1, 10)),
    ("Spare part kit type B", (25, 140), (2, 30)),
    ("Data feed subscription", (60, 300), (1, 3)),
    ("Training workshop seat", (80, 350), (1, 12)),
    ("Machine rental, per day", (110, 520), (1, 15)),
]

# Supplier categories: (description template, unit price range in USD, line ref pattern)
PURCHASE_ITEMS = [
    ("Freight {ref}", (150, 2400), "WB-{n5}"),
    ("Cloud hosting {ref}", (300, 3200), "SUB-{ym}"),
    ("Office supplies order {ref}", (40, 600), "PO-{n4}"),
    ("Maintenance call {ref}", (120, 1500), "SR-{n5}"),
    ("Consulting hours {ref}", (400, 5200), "TS-{n4}"),
    ("Fuel card statement {ref}", (200, 2600), "FC-{n5}"),
    ("Warehouse cleaning {ref}", (180, 900), "WO-{n4}"),
]

# Approximate value of one unit in USD (synthetic market levels).
USD_VALUE = {
    "USD": "1",
    "EUR": "1.085",
    "GBP": "1.27",
    "CHF": "1.13",
    "KZT": "0.00206",
    "AED": "0.2723",
    "JPY": "0.00667",
    "KRW": "0.00073",
    "KWD": "3.25",
    "BHD": "2.65",
}

BASE_CURRENCIES = ["EUR", "USD", "KZT", "JPY", "KWD", "GBP"]
FOREIGN_POOL = {
    "EUR": ["USD", "GBP", "CHF", "JPY"],
    "USD": ["EUR", "JPY", "KWD", "GBP"],
    "KZT": ["USD", "EUR", "AED"],
    "JPY": ["USD", "EUR", "KRW"],
    "KWD": ["USD", "EUR", "BHD"],
    "GBP": ["EUR", "USD", "CHF"],
}
TZ_FOR_BASE = {
    "EUR": ["Europe/Berlin", "UTC"],
    "USD": ["America/New_York", "America/Sao_Paulo", "Asia/Kolkata"],
    "KZT": ["Asia/Almaty"],
    "JPY": ["Asia/Tokyo"],
    "KWD": ["Asia/Kuwait", "Asia/Kathmandu"],
    "GBP": ["Europe/London", "Australia/Sydney"],
}


def syllable_name(rng: random.Random) -> str:
    return (rng.choice(_SYL_A) + rng.choice(_SYL_B)).capitalize()


def company_name(rng: random.Random, tz: str) -> str:
    return f"{syllable_name(rng)} {rng.choice(_INDUSTRY)} {LEGAL_SUFFIX.get(tz, 'Ltd')}"


def counterparty_name(rng: random.Random) -> str:
    return f"{syllable_name(rng)} {syllable_name(rng)} {rng.choice(['Ltd', 'GmbH', 'LLP', 'SA', 'BV', 'AB', 'Oy'])}"
