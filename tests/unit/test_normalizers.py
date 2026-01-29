"""Tests for data normalizers."""

import pytest
from datetime import datetime

from src.cleaning.normalizer import (
    TextNormalizer,
    PriceNormalizer,
    DateNormalizer,
    URLNormalizer,
    NumberNormalizer,
    BooleanNormalizer,
)


class TestTextNormalizer:
    """Tests for TextNormalizer."""

    def test_basic_strip(self):
        """Test basic stripping."""
        normalizer = TextNormalizer()
        assert normalizer.normalize("  hello  ") == "hello"

    def test_remove_extra_whitespace(self):
        """Test removing extra whitespace."""
        normalizer = TextNormalizer(remove_extra_whitespace=True)
        assert normalizer.normalize("hello    world") == "hello world"

    def test_lowercase(self):
        """Test lowercase conversion."""
        normalizer = TextNormalizer(lowercase=True)
        assert normalizer.normalize("HELLO World") == "hello world"

    def test_uppercase(self):
        """Test uppercase conversion."""
        normalizer = TextNormalizer(uppercase=True)
        assert normalizer.normalize("hello world") == "HELLO WORLD"

    def test_max_length(self):
        """Test max length truncation."""
        normalizer = TextNormalizer(max_length=5)
        assert normalizer.normalize("hello world") == "hello"

    def test_none_value(self):
        """Test None value handling."""
        normalizer = TextNormalizer()
        assert normalizer.normalize(None) == ""

    def test_remove_newlines(self):
        """Test newline removal."""
        normalizer = TextNormalizer(remove_newlines=True)
        assert normalizer.normalize("hello\nworld") == "hello world"


class TestPriceNormalizer:
    """Tests for PriceNormalizer."""

    def test_basic_price(self):
        """Test basic price parsing."""
        normalizer = PriceNormalizer()
        assert normalizer.normalize("$19.99") == 19.99

    def test_price_with_currency_symbol(self):
        """Test price with various currency symbols."""
        normalizer = PriceNormalizer()
        assert normalizer.normalize("€29.99") == 29.99
        assert normalizer.normalize("£15.50") == 15.50
        assert normalizer.normalize("₺100.00") == 100.00

    def test_turkish_format(self):
        """Test Turkish price format (1.234,56)."""
        normalizer = PriceNormalizer(handle_turkish=True)
        assert normalizer.normalize("₺1.234,56") == 1234.56

    def test_price_with_thousand_separator(self):
        """Test price with thousand separator."""
        normalizer = PriceNormalizer()
        assert normalizer.normalize("$1,999.99") == 1999.99

    def test_return_dict(self):
        """Test returning dictionary with currency."""
        normalizer = PriceNormalizer(return_float=False)
        result = normalizer.normalize("$19.99")
        assert isinstance(result, dict)
        assert result["amount"] == 19.99
        assert result["currency"] == "USD"

    def test_none_value(self):
        """Test None value handling."""
        normalizer = PriceNormalizer()
        assert normalizer.normalize(None) is None

    def test_invalid_price(self):
        """Test invalid price string."""
        normalizer = PriceNormalizer()
        assert normalizer.normalize("no price here") is None


class TestDateNormalizer:
    """Tests for DateNormalizer."""

    def test_iso_format(self):
        """Test ISO date format."""
        normalizer = DateNormalizer()
        assert normalizer.normalize("2024-01-15") == "2024-01-15"

    def test_european_format(self):
        """Test European date format."""
        normalizer = DateNormalizer()
        assert normalizer.normalize("15/01/2024") == "2024-01-15"

    def test_custom_output_format(self):
        """Test custom output format."""
        normalizer = DateNormalizer(output_format="%d.%m.%Y")
        assert normalizer.normalize("2024-01-15") == "15.01.2024"

    def test_return_datetime(self):
        """Test returning datetime object."""
        normalizer = DateNormalizer(return_datetime=True)
        result = normalizer.normalize("2024-01-15")
        assert isinstance(result, datetime)
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

    def test_relative_today(self):
        """Test 'today' relative date."""
        normalizer = DateNormalizer(return_datetime=True)
        result = normalizer.normalize("today")
        assert result.date() == datetime.now().date()

    def test_none_value(self):
        """Test None value handling."""
        normalizer = DateNormalizer()
        assert normalizer.normalize(None) is None


class TestURLNormalizer:
    """Tests for URLNormalizer."""

    def test_basic_url(self):
        """Test basic URL normalization."""
        normalizer = URLNormalizer()
        assert normalizer.normalize("https://example.com/page") == "https://example.com/page"

    def test_relative_url(self):
        """Test relative URL with base."""
        normalizer = URLNormalizer(base_url="https://example.com")
        assert normalizer.normalize("/page") == "https://example.com/page"

    def test_remove_tracking_params(self):
        """Test removing tracking parameters."""
        normalizer = URLNormalizer(remove_tracking_params=True)
        result = normalizer.normalize("https://example.com/page?utm_source=google&id=123")
        assert "utm_source" not in result
        assert "id=123" in result

    def test_force_https(self):
        """Test forcing HTTPS."""
        normalizer = URLNormalizer(force_https=True)
        assert normalizer.normalize("http://example.com") == "https://example.com"

    def test_remove_fragments(self):
        """Test removing URL fragments."""
        normalizer = URLNormalizer(remove_fragments=True)
        assert normalizer.normalize("https://example.com/page#section") == "https://example.com/page"


class TestNumberNormalizer:
    """Tests for NumberNormalizer."""

    def test_integer(self):
        """Test integer normalization."""
        normalizer = NumberNormalizer(return_type=int)
        assert normalizer.normalize("42") == 42

    def test_float(self):
        """Test float normalization."""
        normalizer = NumberNormalizer(return_type=float)
        assert normalizer.normalize("3.14") == 3.14

    def test_with_text(self):
        """Test extracting number from text."""
        normalizer = NumberNormalizer()
        assert normalizer.normalize("Price: 99.99") == 99.99

    def test_min_max_bounds(self):
        """Test min/max value bounds."""
        normalizer = NumberNormalizer(min_value=0, max_value=100)
        assert normalizer.normalize("-50") == 0
        assert normalizer.normalize("150") == 100

    def test_default_value(self):
        """Test default value for invalid input."""
        normalizer = NumberNormalizer(default=0)
        assert normalizer.normalize("not a number") == 0


class TestBooleanNormalizer:
    """Tests for BooleanNormalizer."""

    def test_true_values(self):
        """Test true value strings."""
        normalizer = BooleanNormalizer()
        assert normalizer.normalize("true") is True
        assert normalizer.normalize("yes") is True
        assert normalizer.normalize("1") is True
        assert normalizer.normalize("on") is True

    def test_false_values(self):
        """Test false value strings."""
        normalizer = BooleanNormalizer()
        assert normalizer.normalize("false") is False
        assert normalizer.normalize("no") is False
        assert normalizer.normalize("0") is False
        assert normalizer.normalize("off") is False

    def test_turkish_values(self):
        """Test Turkish boolean values."""
        normalizer = BooleanNormalizer()
        assert normalizer.normalize("evet") is True
        assert normalizer.normalize("hayır") is False

    def test_default_value(self):
        """Test default value for unknown input."""
        normalizer = BooleanNormalizer(default=False)
        assert normalizer.normalize("maybe") is False
