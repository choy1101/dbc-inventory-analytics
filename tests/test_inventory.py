"""Tests for the Etsy V3 inventory management client."""

import json
import pytest
import responses as responses_lib

from dbc_inventory.inventory.etsy_client import (
    EtsyAPIError,
    EtsyAuthError,
    EtsyInventoryClient,
    Listing,
    ListingImage,
)

# ---------------------------------------------------------------------------
# Fixtures & helpers
# ---------------------------------------------------------------------------

API_KEY = "test-api-key"
ACCESS_TOKEN = "test-access-token"
SHOP_ID = "DivineBeadCraft"
BASE = "https://openapi.etsy.com/v3/application"


def make_client() -> EtsyInventoryClient:
    return EtsyInventoryClient(
        api_key=API_KEY,
        access_token=ACCESS_TOKEN,
        shop_id=SHOP_ID,
    )


def _listing_payload(listing_id: int = 1234, **overrides) -> dict:
    payload = {
        "listing_id": listing_id,
        "title": "Handmade Rosary Beads",
        "description": "Beautiful handmade rosary.",
        "price": {"amount": 2500, "divisor": 100, "currency_code": "USD"},
        "quantity": 10,
        "state": "active",
        "tags": ["rosary beads", "catholic rosary"],
        "url": "https://www.etsy.com/listing/1234",
        "images": [
            {
                "listing_image_id": 9001,
                "url_fullxfull": "https://example.com/img.jpg",
                "rank": 1,
            }
        ],
    }
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# Listing.from_api_response
# ---------------------------------------------------------------------------


class TestListingFromApiResponse:
    def test_basic_fields(self):
        listing = Listing.from_api_response(_listing_payload())
        assert listing.listing_id == 1234
        assert listing.title == "Handmade Rosary Beads"
        assert listing.price == 25.0
        assert listing.currency_code == "USD"
        assert listing.quantity == 10
        assert listing.state == "active"
        assert listing.tags == ["rosary beads", "catholic rosary"]

    def test_images_parsed(self):
        listing = Listing.from_api_response(_listing_payload())
        assert len(listing.images) == 1
        assert listing.images[0].listing_image_id == 9001
        assert listing.images[0].url_fullxfull == "https://example.com/img.jpg"

    def test_missing_images_key(self):
        payload = _listing_payload()
        del payload["images"]
        listing = Listing.from_api_response(payload)
        assert listing.images == []

    def test_price_divisor_zero_uses_fallback(self):
        payload = _listing_payload()
        payload["price"]["divisor"] = 0
        listing = Listing.from_api_response(payload)
        # divisor clamped to 1, so 2500/1 = 2500
        assert listing.price == 2500.0


# ---------------------------------------------------------------------------
# EtsyInventoryClient – read operations
# ---------------------------------------------------------------------------


@responses_lib.activate
class TestGetListing:
    def test_returns_listing(self):
        responses_lib.add(
            responses_lib.GET,
            f"{BASE}/listings/1234",
            json=_listing_payload(),
            status=200,
        )
        client = make_client()
        listing = client.get_listing(1234)
        assert isinstance(listing, Listing)
        assert listing.listing_id == 1234

    def test_sends_api_key_header(self):
        responses_lib.add(
            responses_lib.GET,
            f"{BASE}/listings/1234",
            json=_listing_payload(),
            status=200,
        )
        client = make_client()
        client.get_listing(1234)
        assert responses_lib.calls[0].request.headers["x-api-key"] == API_KEY

    def test_raises_etsy_api_error_on_404(self):
        responses_lib.add(
            responses_lib.GET,
            f"{BASE}/listings/9999",
            json={"error": "Listing not found"},
            status=404,
        )
        client = make_client()
        with pytest.raises(EtsyAPIError) as exc_info:
            client.get_listing(9999)
        assert exc_info.value.status_code == 404

    def test_raises_etsy_auth_error_on_401(self):
        responses_lib.add(
            responses_lib.GET,
            f"{BASE}/listings/1234",
            json={"error": "Unauthorized"},
            status=401,
        )
        client = make_client()
        with pytest.raises(EtsyAuthError):
            client.get_listing(1234)


@responses_lib.activate
class TestGetShopListings:
    def test_returns_list_of_listings(self):
        responses_lib.add(
            responses_lib.GET,
            f"{BASE}/shops/{SHOP_ID}/listings/active",
            json={"results": [_listing_payload(1), _listing_payload(2)]},
            status=200,
        )
        client = make_client()
        listings = client.get_shop_listings()
        assert len(listings) == 2
        assert all(isinstance(l, Listing) for l in listings)

    def test_empty_results(self):
        responses_lib.add(
            responses_lib.GET,
            f"{BASE}/shops/{SHOP_ID}/listings/active",
            json={"results": []},
            status=200,
        )
        client = make_client()
        assert client.get_shop_listings() == []

    def test_state_parameter_in_url(self):
        responses_lib.add(
            responses_lib.GET,
            f"{BASE}/shops/{SHOP_ID}/listings/inactive",
            json={"results": []},
            status=200,
        )
        client = make_client()
        client.get_shop_listings(state="inactive")
        assert f"/listings/inactive" in responses_lib.calls[0].request.url

    def test_limit_capped_at_100(self):
        responses_lib.add(
            responses_lib.GET,
            f"{BASE}/shops/{SHOP_ID}/listings/active",
            json={"results": []},
            status=200,
        )
        client = make_client()
        client.get_shop_listings(limit=200)
        assert "limit=100" in responses_lib.calls[0].request.url


# ---------------------------------------------------------------------------
# EtsyInventoryClient – write operations
# ---------------------------------------------------------------------------


@responses_lib.activate
class TestUpdateListing:
    def test_updates_title(self):
        updated = _listing_payload(title="New Title")
        responses_lib.add(
            responses_lib.PATCH,
            f"{BASE}/shops/{SHOP_ID}/listings/1234",
            json=updated,
            status=200,
        )
        client = make_client()
        listing = client.update_listing(1234, title="New Title")
        assert listing.title == "New Title"

    def test_sends_bearer_token(self):
        responses_lib.add(
            responses_lib.PATCH,
            f"{BASE}/shops/{SHOP_ID}/listings/1234",
            json=_listing_payload(),
            status=200,
        )
        client = make_client()
        client.update_listing(1234, title="Test")
        auth_header = responses_lib.calls[0].request.headers.get("Authorization", "")
        assert auth_header == f"Bearer {ACCESS_TOKEN}"

    def test_raises_value_error_for_no_fields(self):
        client = make_client()
        with pytest.raises(ValueError, match="At least one field"):
            client.update_listing(1234)

    def test_raises_value_error_for_too_many_tags(self):
        client = make_client()
        with pytest.raises(ValueError, match="13 tags"):
            client.update_listing(1234, tags=[f"tag{i}" for i in range(14)])

    def test_raises_etsy_auth_error_on_403(self):
        responses_lib.add(
            responses_lib.PATCH,
            f"{BASE}/shops/{SHOP_ID}/listings/1234",
            json={"error": "Forbidden"},
            status=403,
        )
        client = make_client()
        with pytest.raises(EtsyAuthError):
            client.update_listing(1234, title="Test")


@responses_lib.activate
class TestUpdateQuantity:
    def test_updates_quantity(self):
        updated = _listing_payload(quantity=5)
        responses_lib.add(
            responses_lib.PATCH,
            f"{BASE}/shops/{SHOP_ID}/listings/1234",
            json=updated,
            status=200,
        )
        client = make_client()
        listing = client.update_quantity(1234, 5)
        assert listing.quantity == 5

    def test_negative_quantity_raises(self):
        client = make_client()
        with pytest.raises(ValueError, match="quantity must be"):
            client.update_quantity(1234, -1)

    def test_zero_quantity_allowed(self):
        responses_lib.add(
            responses_lib.PATCH,
            f"{BASE}/shops/{SHOP_ID}/listings/1234",
            json=_listing_payload(quantity=0),
            status=200,
        )
        client = make_client()
        listing = client.update_quantity(1234, 0)
        assert listing.quantity == 0


@responses_lib.activate
class TestUpdateTags:
    def test_replaces_tags(self):
        new_tags = ["handmade rosary", "catholic gift"]
        updated = _listing_payload(tags=new_tags)
        responses_lib.add(
            responses_lib.PATCH,
            f"{BASE}/shops/{SHOP_ID}/listings/1234",
            json=updated,
            status=200,
        )
        client = make_client()
        listing = client.update_tags(1234, new_tags)
        assert listing.tags == new_tags

    def test_too_many_tags_raises(self):
        client = make_client()
        with pytest.raises(ValueError):
            client.update_tags(1234, [f"tag{i}" for i in range(14)])
