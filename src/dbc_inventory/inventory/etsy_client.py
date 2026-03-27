"""Etsy V3 API client for DivineBeadCraft inventory management.

Wraps the Etsy Open API v3 endpoints most relevant to managing a single
shop's active listings: read, create, update, and adjust inventory/quantity.

Etsy API reference: https://developers.etsy.com/documentation/reference
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import requests

logger = logging.getLogger(__name__)

_BASE_URL = "https://openapi.etsy.com/v3/application"
_DEFAULT_TIMEOUT = 15  # seconds


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class ListingImage:
    """A single image attached to an Etsy listing."""

    listing_image_id: int
    url_fullxfull: str
    rank: int = 1


@dataclass
class Listing:
    """Represents an Etsy listing as returned by the V3 API."""

    listing_id: int
    title: str
    description: str
    price: float
    currency_code: str
    quantity: int
    state: str  # "active" | "inactive" | "draft" | "expired"
    tags: list[str] = field(default_factory=list)
    images: list[ListingImage] = field(default_factory=list)
    url: str = ""

    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> "Listing":
        """Build a :class:`Listing` from a raw Etsy API dict."""
        images = [
            ListingImage(
                listing_image_id=img["listing_image_id"],
                url_fullxfull=img.get("url_fullxfull", ""),
                rank=img.get("rank", 1),
            )
            for img in data.get("images", [])
        ]
        price_data = data.get("price", {})
        price_amount = float(price_data.get("amount", 0)) / max(
            int(price_data.get("divisor", 100)), 1
        )
        return cls(
            listing_id=data["listing_id"],
            title=data.get("title", ""),
            description=data.get("description", ""),
            price=price_amount,
            currency_code=price_data.get("currency_code", "USD"),
            quantity=data.get("quantity", 0),
            state=data.get("state", ""),
            tags=data.get("tags", []),
            url=data.get("url", ""),
            images=images,
        )


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class EtsyAPIError(Exception):
    """Raised when the Etsy API returns an unexpected response."""

    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        super().__init__(f"HTTP {status_code}: {message}")


class EtsyAuthError(EtsyAPIError):
    """Raised on authentication / authorisation failures (401/403)."""


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class EtsyInventoryClient:
    """Thin wrapper around the Etsy V3 API for inventory management.

    Parameters
    ----------
    api_key:
        Etsy keystring (public API key).  Required for read operations.
    access_token:
        OAuth2 access token.  Required for write operations.
    shop_id:
        The numeric or string ID of the DivineBeadCraft shop.
    timeout:
        HTTP request timeout in seconds.
    session:
        Optional :class:`requests.Session` to use (useful for testing).
    """

    def __init__(
        self,
        api_key: str,
        access_token: str,
        shop_id: str | int,
        *,
        timeout: int = _DEFAULT_TIMEOUT,
        session: requests.Session | None = None,
    ) -> None:
        self._api_key = api_key
        self._access_token = access_token
        self._shop_id = shop_id
        self._timeout = timeout
        self._session = session or requests.Session()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _headers(self, *, write: bool = False) -> dict[str, str]:
        headers: dict[str, str] = {
            "x-api-key": self._api_key,
            "Accept": "application/json",
        }
        if write:
            headers["Authorization"] = f"Bearer {self._access_token}"
            headers["Content-Type"] = "application/json"
        return headers

    def _request(
        self,
        method: str,
        path: str,
        *,
        write: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any]:
        url = f"{_BASE_URL}{path}"
        response = self._session.request(
            method,
            url,
            headers=self._headers(write=write),
            timeout=self._timeout,
            **kwargs,
        )
        logger.debug("%s %s -> %s", method, url, response.status_code)
        self._raise_for_status(response)
        return response.json()  # type: ignore[no-any-return]

    @staticmethod
    def _raise_for_status(response: requests.Response) -> None:
        if response.ok:
            return
        message = ""
        try:
            message = response.json().get("error", response.text)
        except Exception:
            message = response.text
        if response.status_code in (401, 403):
            raise EtsyAuthError(response.status_code, message)
        raise EtsyAPIError(response.status_code, message)

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def get_listing(self, listing_id: int) -> Listing:
        """Fetch a single listing by its ID.

        Parameters
        ----------
        listing_id:
            The numeric Etsy listing ID.
        """
        data = self._request("GET", f"/listings/{listing_id}", params={"includes": "images"})
        return Listing.from_api_response(data)

    def get_shop_listings(
        self,
        *,
        state: str = "active",
        limit: int = 25,
        offset: int = 0,
    ) -> list[Listing]:
        """Return listings for the configured shop.

        Parameters
        ----------
        state:
            Listing state filter: ``"active"``, ``"inactive"``, ``"draft"``,
            or ``"expired"``.
        limit:
            Page size (1–100).
        offset:
            Pagination offset.
        """
        data = self._request(
            "GET",
            f"/shops/{self._shop_id}/listings/{state}",
            params={"limit": min(limit, 100), "offset": offset, "includes": "images"},
        )
        return [Listing.from_api_response(item) for item in data.get("results", [])]

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def update_listing(
        self,
        listing_id: int,
        *,
        title: str | None = None,
        description: str | None = None,
        tags: list[str] | None = None,
        price: float | None = None,
        quantity: int | None = None,
        state: str | None = None,
    ) -> Listing:
        """Update one or more fields of an existing listing.

        Only the supplied keyword arguments are included in the PATCH body;
        omitted arguments leave those fields unchanged on Etsy.

        Parameters
        ----------
        listing_id:
            Target listing ID.
        title:
            New listing title (max 140 characters on Etsy).
        description:
            New listing description.
        tags:
            Complete replacement tag list (max 13 tags, 20 chars each).
        price:
            New price in the shop's currency.
        quantity:
            New quantity available.
        state:
            New listing state (``"active"`` or ``"inactive"``).
        """
        if tags is not None and len(tags) > 13:
            raise ValueError(f"Etsy allows at most 13 tags; {len(tags)} provided.")

        payload: dict[str, Any] = {}
        if title is not None:
            payload["title"] = title
        if description is not None:
            payload["description"] = description
        if tags is not None:
            payload["tags"] = tags
        if price is not None:
            payload["price"] = price
        if quantity is not None:
            payload["quantity"] = quantity
        if state is not None:
            payload["state"] = state

        if not payload:
            raise ValueError("At least one field must be supplied to update_listing().")

        data = self._request(
            "PATCH",
            f"/shops/{self._shop_id}/listings/{listing_id}",
            write=True,
            json=payload,
        )
        return Listing.from_api_response(data)

    def update_quantity(self, listing_id: int, quantity: int) -> Listing:
        """Convenience wrapper: update only the quantity of a listing.

        Parameters
        ----------
        listing_id:
            Target listing ID.
        quantity:
            New quantity (must be ≥ 0).
        """
        if quantity < 0:
            raise ValueError(f"quantity must be ≥ 0, got {quantity}.")
        return self.update_listing(listing_id, quantity=quantity)

    def update_tags(self, listing_id: int, tags: list[str]) -> Listing:
        """Convenience wrapper: replace all tags on a listing.

        Parameters
        ----------
        listing_id:
            Target listing ID.
        tags:
            New tag list (max 13).
        """
        return self.update_listing(listing_id, tags=tags)
