"""Tests for data cleaning pipeline."""

import pytest

from src.cleaning.pipeline import CleaningPipeline, CleaningStep
from src.cleaning.normalizer import TextNormalizer, PriceNormalizer
from src.cleaning.deduplicator import Deduplicator


class TestCleaningPipeline:
    """Tests for CleaningPipeline."""

    def test_empty_pipeline(self):
        """Test empty pipeline passes data through."""
        pipeline = CleaningPipeline()
        data = {"name": "test", "value": 123}
        result = pipeline.clean(data)
        assert result == data

    def test_single_normalizer(self):
        """Test pipeline with single normalizer."""
        pipeline = CleaningPipeline()
        pipeline.add_normalizer("name", TextNormalizer(strip=True))

        data = {"name": "  hello  ", "value": 123}
        result = pipeline.clean(data)

        assert result["name"] == "hello"
        assert result["value"] == 123

    def test_multiple_normalizers(self):
        """Test pipeline with multiple normalizers."""
        pipeline = CleaningPipeline()
        pipeline.add_normalizer("title", TextNormalizer(strip=True, lowercase=True))
        pipeline.add_normalizer("price", PriceNormalizer(return_float=True))

        data = {"title": "  HELLO WORLD  ", "price": "$19.99"}
        result = pipeline.clean(data)

        assert result["title"] == "hello world"
        assert result["price"] == 19.99

    def test_required_field_missing(self):
        """Test pipeline with required field missing."""
        pipeline = CleaningPipeline()
        pipeline.add_normalizer("name", TextNormalizer(), required=True)

        data = {"other": "value"}
        result = pipeline.clean(data)

        assert result is None  # Filtered out

    def test_required_field_present(self):
        """Test pipeline with required field present."""
        pipeline = CleaningPipeline()
        pipeline.add_normalizer("name", TextNormalizer(), required=True)

        data = {"name": "test"}
        result = pipeline.clean(data)

        assert result is not None
        assert result["name"] == "test"

    def test_default_value(self):
        """Test pipeline with default value."""
        pipeline = CleaningPipeline()
        pipeline.add_normalizer("name", TextNormalizer(), default="unknown")

        data = {"other": "value"}
        result = pipeline.clean(data)

        assert result["name"] == "unknown"

    def test_transform_function(self):
        """Test pipeline with transform function."""
        pipeline = CleaningPipeline()

        def add_computed_field(data):
            data["full_name"] = f"{data.get('first', '')} {data.get('last', '')}"
            return data

        pipeline.add_transform(add_computed_field)

        data = {"first": "John", "last": "Doe"}
        result = pipeline.clean(data)

        assert result["full_name"] == "John Doe"

    def test_filter_function(self):
        """Test pipeline with filter function."""
        pipeline = CleaningPipeline()
        pipeline.add_filter(lambda x: x.get("price", 0) > 10)

        data_pass = {"name": "item1", "price": 20}
        data_fail = {"name": "item2", "price": 5}

        assert pipeline.clean(data_pass) is not None
        assert pipeline.clean(data_fail) is None

    def test_batch_cleaning(self):
        """Test batch cleaning."""
        pipeline = CleaningPipeline()
        pipeline.add_normalizer("price", PriceNormalizer(return_float=True), required=True)
        pipeline.add_filter(lambda x: x.get("price", 0) > 10)

        data = [
            {"name": "item1", "price": "$20"},
            {"name": "item2", "price": "$5"},
            {"name": "item3"},  # Missing price
            {"name": "item4", "price": "$15"},
        ]

        results = pipeline.clean_batch(data)

        assert len(results) == 2  # item2 filtered, item3 missing required
        assert results[0]["name"] == "item1"
        assert results[1]["name"] == "item4"

    def test_callable_interface(self):
        """Test pipeline as callable."""
        pipeline = CleaningPipeline()
        pipeline.add_normalizer("name", TextNormalizer(uppercase=True))

        # Single item
        result = pipeline({"name": "hello"})
        assert result["name"] == "HELLO"

        # Batch
        results = pipeline([{"name": "hello"}, {"name": "world"}])
        assert results[0]["name"] == "HELLO"
        assert results[1]["name"] == "WORLD"


class TestDeduplicator:
    """Tests for Deduplicator."""

    def test_basic_deduplication(self):
        """Test basic deduplication."""
        dedup = Deduplicator(key_fields=["id"])

        data = [
            {"id": 1, "name": "first"},
            {"id": 2, "name": "second"},
            {"id": 1, "name": "duplicate"},
        ]

        results = dedup.deduplicate(data)

        assert len(results) == 2
        assert results[0]["name"] == "first"
        assert results[1]["name"] == "second"

    def test_keep_last(self):
        """Test keeping last duplicate."""
        dedup = Deduplicator(key_fields=["id"])

        data = [
            {"id": 1, "name": "first"},
            {"id": 1, "name": "last"},
        ]

        results = dedup.deduplicate(data, keep="last")

        assert len(results) == 1
        assert results[0]["name"] == "last"

    def test_multiple_key_fields(self):
        """Test deduplication with multiple key fields."""
        dedup = Deduplicator(key_fields=["category", "name"])

        data = [
            {"category": "A", "name": "item1", "value": 1},
            {"category": "A", "name": "item2", "value": 2},
            {"category": "A", "name": "item1", "value": 3},  # Duplicate
            {"category": "B", "name": "item1", "value": 4},  # Different category
        ]

        results = dedup.deduplicate(data)

        assert len(results) == 3

    def test_case_insensitive(self):
        """Test case insensitive deduplication."""
        dedup = Deduplicator(key_fields=["name"], case_sensitive=False)

        data = [
            {"name": "Test"},
            {"name": "TEST"},
            {"name": "test"},
        ]

        results = dedup.deduplicate(data)

        assert len(results) == 1

    def test_mark_duplicates(self):
        """Test marking duplicates instead of removing."""
        dedup = Deduplicator(key_fields=["id"])

        data = [
            {"id": 1, "name": "first"},
            {"id": 1, "name": "duplicate"},
        ]

        results = dedup.deduplicate(data, mark_duplicates=True)

        assert len(results) == 2
        assert results[0]["_is_duplicate"] is False
        assert results[1]["_is_duplicate"] is True

    def test_is_duplicate_check(self):
        """Test is_duplicate method."""
        dedup = Deduplicator(key_fields=["id"])

        dedup.add({"id": 1})

        assert dedup.is_duplicate({"id": 1}) is True
        assert dedup.is_duplicate({"id": 2}) is False

    def test_hash_generation(self):
        """Test hash is added to results."""
        dedup = Deduplicator(key_fields=["id"])

        data = [{"id": 1}]
        results = dedup.deduplicate(data)

        assert "_hash" in results[0]
        assert len(results[0]["_hash"]) == 64  # SHA256 hex

    def test_reset(self):
        """Test resetting seen hashes."""
        dedup = Deduplicator(key_fields=["id"])

        dedup.add({"id": 1})
        assert dedup.seen_count == 1

        dedup.reset()
        assert dedup.seen_count == 0
