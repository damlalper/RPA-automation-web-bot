"""Data normalizers for different data types."""

import re
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any
from urllib.parse import urljoin, urlparse

from src.monitoring.logger import get_logger

logger = get_logger(__name__)


class BaseNormalizer(ABC):
    """Base class for normalizers."""

    @abstractmethod
    def normalize(self, value: Any) -> Any:
        """Normalize value.

        Args:
            value: Value to normalize

        Returns:
            Normalized value
        """
        pass

    def __call__(self, value: Any) -> Any:
        """Allow normalizer to be called directly.

        Args:
            value: Value to normalize

        Returns:
            Normalized value
        """
        return self.normalize(value)


class TextNormalizer(BaseNormalizer):
    """Normalizer for text data."""

    def __init__(
        self,
        strip: bool = True,
        lowercase: bool = False,
        uppercase: bool = False,
        remove_extra_whitespace: bool = True,
        remove_newlines: bool = False,
        remove_special_chars: bool = False,
        allowed_chars: str | None = None,
        max_length: int | None = None,
    ) -> None:
        """Initialize text normalizer.

        Args:
            strip: Strip leading/trailing whitespace
            lowercase: Convert to lowercase
            uppercase: Convert to uppercase
            remove_extra_whitespace: Replace multiple spaces with single
            remove_newlines: Remove newline characters
            remove_special_chars: Remove special characters
            allowed_chars: Characters to allow (regex pattern)
            max_length: Truncate to max length
        """
        self.strip = strip
        self.lowercase = lowercase
        self.uppercase = uppercase
        self.remove_extra_whitespace = remove_extra_whitespace
        self.remove_newlines = remove_newlines
        self.remove_special_chars = remove_special_chars
        self.allowed_chars = allowed_chars
        self.max_length = max_length

    def normalize(self, value: Any) -> str:
        """Normalize text value.

        Args:
            value: Value to normalize

        Returns:
            Normalized text string
        """
        if value is None:
            return ""

        text = str(value)

        if self.strip:
            text = text.strip()

        if self.remove_newlines:
            text = text.replace("\n", " ").replace("\r", "")

        if self.remove_extra_whitespace:
            text = re.sub(r"\s+", " ", text)

        if self.remove_special_chars:
            text = re.sub(r"[^\w\s]", "", text)

        if self.allowed_chars:
            text = re.sub(f"[^{self.allowed_chars}]", "", text)

        if self.lowercase:
            text = text.lower()
        elif self.uppercase:
            text = text.upper()

        if self.max_length and len(text) > self.max_length:
            text = text[: self.max_length]

        return text


class PriceNormalizer(BaseNormalizer):
    """Normalizer for price/currency data."""

    # Currency symbols and their codes
    CURRENCY_MAP = {
        "$": "USD",
        "€": "EUR",
        "£": "GBP",
        "₺": "TRY",
        "¥": "JPY",
        "₹": "INR",
        "₽": "RUB",
        "kr": "SEK",
        "CHF": "CHF",
    }

    def __init__(
        self,
        decimal_separator: str = ".",
        thousand_separator: str = ",",
        currency_code: str | None = None,
        return_float: bool = True,
        handle_turkish: bool = True,
    ) -> None:
        """Initialize price normalizer.

        Args:
            decimal_separator: Character for decimal point
            thousand_separator: Character for thousands
            currency_code: Expected currency code
            return_float: Return float instead of dict
            handle_turkish: Handle Turkish format (1.234,56)
        """
        self.decimal_separator = decimal_separator
        self.thousand_separator = thousand_separator
        self.currency_code = currency_code
        self.return_float = return_float
        self.handle_turkish = handle_turkish

    def normalize(self, value: Any) -> float | dict[str, Any] | None:
        """Normalize price value.

        Args:
            value: Price string to normalize

        Returns:
            Float price or dict with price and currency, or None
        """
        if value is None:
            return None

        text = str(value).strip()
        if not text:
            return None

        # Detect currency
        currency = self.currency_code
        for symbol, code in self.CURRENCY_MAP.items():
            if symbol in text:
                currency = code
                text = text.replace(symbol, "")
                break

        # Remove currency codes
        text = re.sub(r"[A-Z]{3}", "", text).strip()

        # Handle Turkish/European format (1.234,56)
        if self.handle_turkish and "," in text and "." in text:
            # Check if comma comes after dot (Turkish format)
            if text.rfind(",") > text.rfind("."):
                text = text.replace(".", "").replace(",", ".")

        # Standard cleaning
        text = text.replace(self.thousand_separator, "")
        if self.decimal_separator != ".":
            text = text.replace(self.decimal_separator, ".")

        # Extract numeric value
        match = re.search(r"[\d.]+", text)
        if not match:
            return None

        try:
            price = float(match.group())
        except ValueError:
            return None

        if self.return_float:
            return price

        return {
            "amount": price,
            "currency": currency,
            "original": str(value),
        }


class DateNormalizer(BaseNormalizer):
    """Normalizer for date/time data."""

    # Common date formats
    FORMATS = [
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%m-%d-%Y",
        "%Y/%m/%d",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%Y.%m.%d",
        "%d.%m.%Y",
        "%B %d, %Y",
        "%b %d, %Y",
        "%d %B %Y",
        "%d %b %Y",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S",
    ]

    def __init__(
        self,
        output_format: str = "%Y-%m-%d",
        input_formats: list[str] | None = None,
        return_datetime: bool = False,
    ) -> None:
        """Initialize date normalizer.

        Args:
            output_format: Desired output format
            input_formats: List of input formats to try
            return_datetime: Return datetime object instead of string
        """
        self.output_format = output_format
        self.input_formats = input_formats or self.FORMATS
        self.return_datetime = return_datetime

    def normalize(self, value: Any) -> str | datetime | None:
        """Normalize date value.

        Args:
            value: Date string to normalize

        Returns:
            Normalized date string or datetime object, or None
        """
        if value is None:
            return None

        if isinstance(value, datetime):
            if self.return_datetime:
                return value
            return value.strftime(self.output_format)

        text = str(value).strip()
        if not text:
            return None

        # Try each format
        for fmt in self.input_formats:
            try:
                dt = datetime.strptime(text, fmt)
                if self.return_datetime:
                    return dt
                return dt.strftime(self.output_format)
            except ValueError:
                continue

        # Try relative dates
        relative_date = self._parse_relative_date(text)
        if relative_date:
            if self.return_datetime:
                return relative_date
            return relative_date.strftime(self.output_format)

        logger.debug(f"Could not parse date: {value}")
        return None

    def _parse_relative_date(self, text: str) -> datetime | None:
        """Parse relative date expressions.

        Args:
            text: Text like "2 days ago", "yesterday"

        Returns:
            Datetime or None
        """
        from datetime import timedelta

        text = text.lower()
        now = datetime.now()

        if "today" in text:
            return now
        if "yesterday" in text:
            return now - timedelta(days=1)

        # Pattern: X days/hours/minutes ago
        match = re.search(r"(\d+)\s*(day|hour|minute|week|month)s?\s*ago", text)
        if match:
            amount = int(match.group(1))
            unit = match.group(2)

            if unit == "day":
                return now - timedelta(days=amount)
            elif unit == "hour":
                return now - timedelta(hours=amount)
            elif unit == "minute":
                return now - timedelta(minutes=amount)
            elif unit == "week":
                return now - timedelta(weeks=amount)
            elif unit == "month":
                return now - timedelta(days=amount * 30)

        return None


class URLNormalizer(BaseNormalizer):
    """Normalizer for URLs."""

    def __init__(
        self,
        base_url: str | None = None,
        remove_fragments: bool = True,
        remove_tracking_params: bool = True,
        force_https: bool = False,
    ) -> None:
        """Initialize URL normalizer.

        Args:
            base_url: Base URL for relative links
            remove_fragments: Remove URL fragments (#...)
            remove_tracking_params: Remove tracking parameters
            force_https: Convert http to https
        """
        self.base_url = base_url
        self.remove_fragments = remove_fragments
        self.remove_tracking_params = remove_tracking_params
        self.force_https = force_https

        # Common tracking parameters
        self.tracking_params = {
            "utm_source",
            "utm_medium",
            "utm_campaign",
            "utm_term",
            "utm_content",
            "fbclid",
            "gclid",
            "ref",
            "source",
        }

    def normalize(self, value: Any) -> str | None:
        """Normalize URL.

        Args:
            value: URL string to normalize

        Returns:
            Normalized URL or None
        """
        if value is None:
            return None

        url = str(value).strip()
        if not url:
            return None

        # Handle relative URLs
        if self.base_url and not url.startswith(("http://", "https://", "//")):
            url = urljoin(self.base_url, url)

        # Parse URL
        try:
            parsed = urlparse(url)
        except Exception:
            return url

        # Force HTTPS
        scheme = parsed.scheme
        if self.force_https and scheme == "http":
            scheme = "https"

        # Handle fragment
        fragment = "" if self.remove_fragments else parsed.fragment

        # Handle query parameters
        query = parsed.query
        if self.remove_tracking_params and query:
            from urllib.parse import parse_qs, urlencode

            params = parse_qs(query)
            filtered_params = {k: v for k, v in params.items() if k not in self.tracking_params}
            query = urlencode(filtered_params, doseq=True)

        # Rebuild URL
        from urllib.parse import urlunparse

        return urlunparse((scheme, parsed.netloc, parsed.path, parsed.params, query, fragment))


class NumberNormalizer(BaseNormalizer):
    """Normalizer for numeric data."""

    def __init__(
        self,
        return_type: type = float,
        default: float | int | None = None,
        min_value: float | None = None,
        max_value: float | None = None,
    ) -> None:
        """Initialize number normalizer.

        Args:
            return_type: Desired return type (int or float)
            default: Default value if parsing fails
            min_value: Minimum allowed value
            max_value: Maximum allowed value
        """
        self.return_type = return_type
        self.default = default
        self.min_value = min_value
        self.max_value = max_value

    def normalize(self, value: Any) -> float | int | None:
        """Normalize numeric value.

        Args:
            value: Value to normalize

        Returns:
            Normalized number or default/None
        """
        if value is None:
            return self.default

        if isinstance(value, (int, float)):
            num = value
        else:
            text = str(value).strip()
            # Extract number from text
            text = text.replace(",", ".")
            match = re.search(r"-?[\d.]+", text)
            if not match:
                return self.default
            try:
                num = float(match.group())
            except ValueError:
                return self.default

        # Apply bounds
        if self.min_value is not None:
            num = max(num, self.min_value)
        if self.max_value is not None:
            num = min(num, self.max_value)

        return self.return_type(num)


class BooleanNormalizer(BaseNormalizer):
    """Normalizer for boolean data."""

    TRUE_VALUES = {"true", "yes", "1", "on", "evet", "doğru"}
    FALSE_VALUES = {"false", "no", "0", "off", "hayır", "yanlış"}

    def __init__(self, default: bool | None = None) -> None:
        """Initialize boolean normalizer.

        Args:
            default: Default value if parsing fails
        """
        self.default = default

    def normalize(self, value: Any) -> bool | None:
        """Normalize boolean value.

        Args:
            value: Value to normalize

        Returns:
            Boolean or default/None
        """
        if value is None:
            return self.default

        if isinstance(value, bool):
            return value

        text = str(value).strip().lower()

        if text in self.TRUE_VALUES:
            return True
        if text in self.FALSE_VALUES:
            return False

        return self.default
