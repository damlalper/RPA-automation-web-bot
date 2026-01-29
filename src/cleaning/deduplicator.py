"""Data deduplication utilities."""

import hashlib
from typing import Any, Callable

from src.monitoring.logger import get_logger

logger = get_logger(__name__)


class Deduplicator:
    """Handles data deduplication based on configurable keys."""

    def __init__(
        self,
        key_fields: list[str] | None = None,
        hash_func: Callable[[dict[str, Any]], str] | None = None,
        case_sensitive: bool = False,
    ) -> None:
        """Initialize deduplicator.

        Args:
            key_fields: Fields to use for generating unique key
            hash_func: Custom hash function
            case_sensitive: Whether comparison is case-sensitive
        """
        self.key_fields = key_fields
        self.hash_func = hash_func
        self.case_sensitive = case_sensitive
        self._seen_hashes: set[str] = set()

    def generate_hash(self, data: dict[str, Any]) -> str:
        """Generate hash for data record.

        Args:
            data: Data dictionary

        Returns:
            Hash string
        """
        if self.hash_func:
            return self.hash_func(data)

        # Use specified key fields or all fields
        if self.key_fields:
            key_data = {k: data.get(k) for k in self.key_fields}
        else:
            key_data = data

        # Normalize for comparison
        normalized = {}
        for k, v in key_data.items():
            if v is None:
                normalized[k] = ""
            elif isinstance(v, str):
                normalized[k] = v if self.case_sensitive else v.lower()
            else:
                normalized[k] = str(v)

        # Generate hash
        content = str(sorted(normalized.items()))
        return hashlib.sha256(content.encode()).hexdigest()

    def is_duplicate(self, data: dict[str, Any]) -> bool:
        """Check if data is duplicate.

        Args:
            data: Data dictionary

        Returns:
            True if duplicate
        """
        hash_value = self.generate_hash(data)
        return hash_value in self._seen_hashes

    def add(self, data: dict[str, Any]) -> bool:
        """Add data to seen set.

        Args:
            data: Data dictionary

        Returns:
            True if new (not duplicate)
        """
        hash_value = self.generate_hash(data)
        if hash_value in self._seen_hashes:
            return False
        self._seen_hashes.add(hash_value)
        return True

    def check_and_add(self, data: dict[str, Any]) -> tuple[bool, str]:
        """Check if duplicate and add to seen set.

        Args:
            data: Data dictionary

        Returns:
            Tuple of (is_new, hash)
        """
        hash_value = self.generate_hash(data)
        is_new = hash_value not in self._seen_hashes
        self._seen_hashes.add(hash_value)
        return is_new, hash_value

    def deduplicate(
        self,
        data: list[dict[str, Any]],
        keep: str = "first",
        mark_duplicates: bool = False,
    ) -> list[dict[str, Any]]:
        """Remove duplicates from data list.

        Args:
            data: List of data dictionaries
            keep: Which duplicate to keep ("first" or "last")
            mark_duplicates: Add is_duplicate field instead of removing

        Returns:
            Deduplicated list
        """
        if keep == "last":
            data = list(reversed(data))

        self.reset()
        results = []
        duplicates = 0

        for record in data:
            is_new, hash_value = self.check_and_add(record)

            if mark_duplicates:
                record["_hash"] = hash_value
                record["_is_duplicate"] = not is_new
                results.append(record)
                if not is_new:
                    duplicates += 1
            else:
                if is_new:
                    record["_hash"] = hash_value
                    results.append(record)
                else:
                    duplicates += 1

        if keep == "last":
            results = list(reversed(results))

        logger.info(f"Deduplication complete | input={len(data)} | duplicates={duplicates} | output={len(results)}")

        return results

    def reset(self) -> None:
        """Reset seen hashes."""
        self._seen_hashes.clear()

    @property
    def seen_count(self) -> int:
        """Get count of seen items.

        Returns:
            Number of unique items seen
        """
        return len(self._seen_hashes)

    def get_seen_hashes(self) -> set[str]:
        """Get copy of seen hashes.

        Returns:
            Set of seen hashes
        """
        return set(self._seen_hashes)

    def load_hashes(self, hashes: set[str] | list[str]) -> None:
        """Load existing hashes.

        Args:
            hashes: Set or list of hashes to load
        """
        self._seen_hashes.update(hashes)
        logger.debug(f"Loaded {len(hashes)} existing hashes")


class IncrementalDeduplicator(Deduplicator):
    """Deduplicator with persistence support."""

    def __init__(
        self,
        key_fields: list[str] | None = None,
        storage_path: str | None = None,
        **kwargs,
    ) -> None:
        """Initialize incremental deduplicator.

        Args:
            key_fields: Fields to use for generating unique key
            storage_path: Path to store/load hashes
            **kwargs: Additional arguments for base class
        """
        super().__init__(key_fields=key_fields, **kwargs)
        self.storage_path = storage_path
        if storage_path:
            self._load_from_file()

    def _load_from_file(self) -> None:
        """Load hashes from file."""
        if not self.storage_path:
            return

        try:
            from pathlib import Path

            path = Path(self.storage_path)
            if path.exists():
                with open(path, "r") as f:
                    hashes = {line.strip() for line in f if line.strip()}
                self._seen_hashes.update(hashes)
                logger.info(f"Loaded {len(hashes)} hashes from {path}")
        except Exception as e:
            logger.warning(f"Failed to load hashes from file: {e}")

    def save(self) -> None:
        """Save hashes to file."""
        if not self.storage_path:
            return

        try:
            from pathlib import Path

            path = Path(self.storage_path)
            path.parent.mkdir(parents=True, exist_ok=True)

            with open(path, "w") as f:
                for hash_value in self._seen_hashes:
                    f.write(f"{hash_value}\n")

            logger.info(f"Saved {len(self._seen_hashes)} hashes to {path}")
        except Exception as e:
            logger.warning(f"Failed to save hashes to file: {e}")

    def add(self, data: dict[str, Any], auto_save: bool = False) -> bool:
        """Add data and optionally save.

        Args:
            data: Data dictionary
            auto_save: Save to file after adding

        Returns:
            True if new (not duplicate)
        """
        result = super().add(data)
        if auto_save and result:
            self.save()
        return result


def deduplicate_by_field(
    data: list[dict[str, Any]],
    field: str,
    keep: str = "first",
) -> list[dict[str, Any]]:
    """Simple deduplication by single field.

    Args:
        data: List of data dictionaries
        field: Field name to deduplicate by
        keep: Which duplicate to keep ("first" or "last")

    Returns:
        Deduplicated list
    """
    dedup = Deduplicator(key_fields=[field])
    return dedup.deduplicate(data, keep=keep)


def find_duplicates(
    data: list[dict[str, Any]],
    key_fields: list[str] | None = None,
) -> list[list[dict[str, Any]]]:
    """Find groups of duplicates.

    Args:
        data: List of data dictionaries
        key_fields: Fields to use for comparison

    Returns:
        List of duplicate groups
    """
    dedup = Deduplicator(key_fields=key_fields)
    groups: dict[str, list[dict[str, Any]]] = {}

    for record in data:
        hash_value = dedup.generate_hash(record)
        if hash_value not in groups:
            groups[hash_value] = []
        groups[hash_value].append(record)

    # Return only groups with duplicates
    return [group for group in groups.values() if len(group) > 1]
