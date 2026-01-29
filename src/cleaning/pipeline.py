"""Data cleaning pipeline."""

from dataclasses import dataclass, field
from typing import Any, Callable

from src.monitoring.logger import get_logger

from .normalizer import BaseNormalizer

logger = get_logger(__name__)


@dataclass
class CleaningStep:
    """Single step in cleaning pipeline."""

    name: str
    field: str | None = None  # None means apply to all fields
    normalizer: BaseNormalizer | Callable[[Any], Any] | None = None
    transform: Callable[[dict[str, Any]], dict[str, Any]] | None = None
    filter_func: Callable[[dict[str, Any]], bool] | None = None
    required: bool = False
    default: Any = None

    def apply(self, data: dict[str, Any]) -> dict[str, Any] | None:
        """Apply cleaning step to data.

        Args:
            data: Data dictionary

        Returns:
            Cleaned data or None if filtered out
        """
        # Apply filter
        if self.filter_func and not self.filter_func(data):
            return None

        # Apply transform (whole record)
        if self.transform:
            data = self.transform(data)

        # Apply normalizer to specific field
        if self.field and self.normalizer:
            value = data.get(self.field)

            if value is None:
                if self.required:
                    return None
                data[self.field] = self.default
            else:
                if callable(self.normalizer):
                    data[self.field] = self.normalizer(value)

        return data


@dataclass
class FieldMapping:
    """Field mapping and normalization configuration."""

    source: str
    target: str | None = None  # None keeps same name
    normalizer: BaseNormalizer | Callable[[Any], Any] | None = None
    required: bool = False
    default: Any = None

    @property
    def target_field(self) -> str:
        """Get target field name.

        Returns:
            Target field name
        """
        return self.target or self.source


class CleaningPipeline:
    """Pipeline for cleaning and transforming scraped data."""

    def __init__(self, name: str = "default") -> None:
        """Initialize cleaning pipeline.

        Args:
            name: Pipeline name for logging
        """
        self.name = name
        self._steps: list[CleaningStep] = []
        self._field_mappings: list[FieldMapping] = []
        self._global_transforms: list[Callable[[dict[str, Any]], dict[str, Any]]] = []
        self._filters: list[Callable[[dict[str, Any]], bool]] = []

    def add_step(self, step: CleaningStep) -> "CleaningPipeline":
        """Add cleaning step to pipeline.

        Args:
            step: CleaningStep to add

        Returns:
            Self for chaining
        """
        self._steps.append(step)
        return self

    def add_normalizer(
        self,
        field: str,
        normalizer: BaseNormalizer | Callable[[Any], Any],
        required: bool = False,
        default: Any = None,
    ) -> "CleaningPipeline":
        """Add field normalizer.

        Args:
            field: Field name
            normalizer: Normalizer or callable
            required: Whether field is required
            default: Default value if missing

        Returns:
            Self for chaining
        """
        step = CleaningStep(
            name=f"normalize_{field}",
            field=field,
            normalizer=normalizer,
            required=required,
            default=default,
        )
        self._steps.append(step)
        return self

    def add_transform(
        self,
        transform: Callable[[dict[str, Any]], dict[str, Any]],
        name: str = "transform",
    ) -> "CleaningPipeline":
        """Add global transform function.

        Args:
            transform: Transform function
            name: Transform name

        Returns:
            Self for chaining
        """
        self._global_transforms.append(transform)
        step = CleaningStep(name=name, transform=transform)
        self._steps.append(step)
        return self

    def add_filter(
        self,
        filter_func: Callable[[dict[str, Any]], bool],
        name: str = "filter",
    ) -> "CleaningPipeline":
        """Add filter function.

        Args:
            filter_func: Filter function (return True to keep)
            name: Filter name

        Returns:
            Self for chaining
        """
        self._filters.append(filter_func)
        step = CleaningStep(name=name, filter_func=filter_func)
        self._steps.append(step)
        return self

    def add_field_mapping(self, mapping: FieldMapping) -> "CleaningPipeline":
        """Add field mapping.

        Args:
            mapping: FieldMapping configuration

        Returns:
            Self for chaining
        """
        self._field_mappings.append(mapping)
        return self

    def map_fields(
        self,
        mappings: dict[str, str | tuple[str, BaseNormalizer | None]],
    ) -> "CleaningPipeline":
        """Add multiple field mappings.

        Args:
            mappings: Dict of source -> target or source -> (target, normalizer)

        Returns:
            Self for chaining
        """
        for source, config in mappings.items():
            if isinstance(config, str):
                self._field_mappings.append(FieldMapping(source=source, target=config))
            elif isinstance(config, tuple):
                target, normalizer = config
                self._field_mappings.append(
                    FieldMapping(source=source, target=target, normalizer=normalizer)
                )
        return self

    def clean(self, data: dict[str, Any]) -> dict[str, Any] | None:
        """Clean single data record.

        Args:
            data: Data dictionary

        Returns:
            Cleaned data or None if filtered out
        """
        result = dict(data)

        # Apply field mappings first
        if self._field_mappings:
            mapped = {}
            for mapping in self._field_mappings:
                value = result.get(mapping.source)

                if value is None:
                    if mapping.required:
                        return None
                    value = mapping.default
                elif mapping.normalizer:
                    value = mapping.normalizer(value)

                mapped[mapping.target_field] = value

            result = mapped

        # Apply steps
        for step in self._steps:
            result = step.apply(result)
            if result is None:
                logger.debug(f"Record filtered out at step: {step.name}")
                return None

        return result

    def clean_batch(
        self,
        data: list[dict[str, Any]],
        stop_on_error: bool = False,
    ) -> list[dict[str, Any]]:
        """Clean batch of data records.

        Args:
            data: List of data dictionaries
            stop_on_error: Stop processing on first error

        Returns:
            List of cleaned data (filtered records excluded)
        """
        results = []
        errors = 0

        for i, record in enumerate(data):
            try:
                cleaned = self.clean(record)
                if cleaned is not None:
                    results.append(cleaned)
            except Exception as e:
                errors += 1
                logger.warning(f"Cleaning error at index {i}: {e}")
                if stop_on_error:
                    raise

        logger.info(
            f"Pipeline '{self.name}' completed | "
            f"input={len(data)} | output={len(results)} | "
            f"filtered={len(data) - len(results) - errors} | errors={errors}"
        )

        return results

    def __call__(self, data: dict[str, Any] | list[dict[str, Any]]) -> Any:
        """Allow pipeline to be called directly.

        Args:
            data: Single record or list of records

        Returns:
            Cleaned data
        """
        if isinstance(data, list):
            return self.clean_batch(data)
        return self.clean(data)


# Pre-built pipelines
def create_ecommerce_pipeline() -> CleaningPipeline:
    """Create pipeline for e-commerce data.

    Returns:
        Configured CleaningPipeline
    """
    from .normalizer import PriceNormalizer, TextNormalizer, URLNormalizer

    pipeline = CleaningPipeline(name="ecommerce")

    pipeline.add_normalizer("title", TextNormalizer(strip=True, remove_extra_whitespace=True))
    pipeline.add_normalizer("price", PriceNormalizer(return_float=True), required=True)
    pipeline.add_normalizer("url", URLNormalizer(remove_tracking_params=True))
    pipeline.add_normalizer("description", TextNormalizer(strip=True, max_length=500))

    # Filter out items without price
    pipeline.add_filter(lambda x: x.get("price") is not None and x.get("price") > 0)

    return pipeline


def create_article_pipeline() -> CleaningPipeline:
    """Create pipeline for article/news data.

    Returns:
        Configured CleaningPipeline
    """
    from .normalizer import DateNormalizer, TextNormalizer, URLNormalizer

    pipeline = CleaningPipeline(name="article")

    pipeline.add_normalizer("title", TextNormalizer(strip=True), required=True)
    pipeline.add_normalizer("content", TextNormalizer(strip=True, remove_extra_whitespace=True))
    pipeline.add_normalizer("date", DateNormalizer())
    pipeline.add_normalizer("url", URLNormalizer())
    pipeline.add_normalizer("author", TextNormalizer(strip=True))

    return pipeline
