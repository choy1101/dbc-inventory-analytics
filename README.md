# DBC Inventory Analytics

Private administrative tool for managing SEO, market research, and inventory for the Etsy shop **[DivineBeadCraft](https://www.etsy.com/shop/DivineBeadCraft)**.

## Overview

This application is a private, non-commercial tool developed specifically for the DivineBeadCraft Etsy shop. It provides three core capabilities:

| Module | Purpose |
|---|---|
| `dbc_inventory.seo` | Analyse high-performing keywords for religious-jewellery listings |
| `dbc_inventory.market_research` | Monitor 2026 trends in the Rosary and handmade-craft niche |
| `dbc_inventory.inventory` | Streamline shop updates via the Etsy V3 API |

---

## Installation

Requires **Python 3.10+** and [pip](https://pip.pypa.io/).

```bash
# Install in editable mode (development)
pip install -e ".[dev]"
```

---

## Usage

### SEO Optimisation

```python
from dbc_inventory.seo.keyword_analyzer import analyse_listing, suggest_tags

# Analyse an existing listing
report = analyse_listing(
    title="Handmade Catholic Rosary Beads – Crystal & Gemstone",
    tags=["rosary beads", "prayer beads", "catholic gift"],
)

print(report.summary())

# Get tag suggestions to fill the remaining Etsy tag slots
suggestions = suggest_tags(
    "Handmade Catholic Rosary Beads",
    current_tags=["rosary beads", "prayer beads"],
    max_suggestions=5,
)
print("Suggested tags:", suggestions)
```

### Market Research

```python
from datetime import datetime, timezone
from dbc_inventory.market_research.trend_monitor import TrendMonitor

monitor = TrendMonitor()

# Record weekly search-volume snapshots
monitor.record("rosary beads", 45_000)
monitor.record("rosary beads", 47_500)   # one week later
monitor.record("chaplet", 4_000)
monitor.record("chaplet", 3_800)

# Surface the fastest-rising keywords
for result in monitor.top_trending(n=5):
    print(result)
```

### Inventory Management

```python
from dbc_inventory.inventory.etsy_client import EtsyInventoryClient

client = EtsyInventoryClient(
    api_key="<your-etsy-api-key>",
    access_token="<your-oauth2-access-token>",
    shop_id="DivineBeadCraft",
)

# List active listings
listings = client.get_shop_listings(state="active", limit=25)

# Bulk-update tags on a listing
client.update_tags(listing_id=123456789, tags=["rosary beads", "catholic rosary", "handmade rosary"])

# Adjust quantity after a sale
client.update_quantity(listing_id=123456789, quantity=9)
```

---

## Running Tests

```bash
pytest
```

---

## Compliance & Privacy

- **Data Usage:** This app only accesses data associated with the DivineBeadCraft shop.
- **Third-Party Sharing:** No data is shared, sold, or transmitted to third parties.
- **Trademark:** The term *Etsy* is a trademark of Etsy, Inc. This application uses the Etsy API but is not endorsed or certified by Etsy, Inc.

---

**Developer:** [Shirley/choy1101](https://github.com/choy1101)  
**Status:** Internal Tool – Private Use Only
