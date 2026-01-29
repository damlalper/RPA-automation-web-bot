"""E-commerce scraper example - Books to Scrape.

This example demonstrates:
- Selenium-based web scraping
- Pagination handling
- Data extraction and cleaning
- Database storage (separate tables for pages and books)
- Progress monitoring

Usage:
    python -m examples.ecommerce_scraper.run
"""

import asyncio
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.automation.browser import BrowserManager
from src.cleaning.pipeline import CleaningPipeline
from src.cleaning.normalizer import PriceNormalizer, TextNormalizer, URLNormalizer
from src.cleaning.deduplicator import Deduplicator
from src.core.config import settings
from src.database.connection import get_db_context, init_db
from src.database.models import TaskType
from src.database.repository import BookRepository, ScrapedPageRepository, TaskRepository
from src.monitoring.logger import get_logger, setup_logging
from src.scraping.engine import ScrapingConfig, ScrapingEngine
from src.scraping.pagination import PaginationType

logger = get_logger(__name__)

# Configuration
MAX_PAGES = 20
PAGE_DELAY = 1.0


def extract_rating(class_attr) -> int:
    """Extract star rating from CSS class.

    Args:
        class_attr: CSS class string like "star-rating Three" or list ['star-rating', 'Three']

    Returns:
        Rating as integer (1-5)
    """
    rating_map = {
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
    }

    if not class_attr:
        return 0

    # Handle list input (BeautifulSoup returns list for class attribute)
    if isinstance(class_attr, list):
        class_attr = " ".join(class_attr)

    for word, rating in rating_map.items():
        if word in class_attr.lower():
            return rating
    return 0


def create_cleaning_pipeline() -> CleaningPipeline:
    """Create data cleaning pipeline for book data."""
    pipeline = CleaningPipeline(name="books")

    # Title normalizer
    pipeline.add_normalizer("title", TextNormalizer(strip=True))

    # Price normalizer (£ pounds)
    pipeline.add_normalizer(
        "price",
        PriceNormalizer(currency_code="GBP", return_float=True),
        required=True,
    )

    # Availability normalizer
    pipeline.add_normalizer(
        "availability",
        TextNormalizer(strip=True, remove_extra_whitespace=True),
    )

    # URL normalizer
    pipeline.add_normalizer(
        "link",
        URLNormalizer(base_url="https://books.toscrape.com/catalogue/"),
    )
    pipeline.add_normalizer(
        "image",
        URLNormalizer(base_url="https://books.toscrape.com/"),
    )

    # Custom rating transform
    def transform_rating(data: dict) -> dict:
        rating_str = data.get("rating", "")
        data["rating"] = extract_rating(rating_str)
        return data

    pipeline.add_transform(transform_rating, name="rating_transform")

    # Filter out items without price
    pipeline.add_filter(
        lambda x: x.get("price") is not None and x.get("price") > 0,
        name="price_filter",
    )

    return pipeline


async def run_scraper():
    """Run the e-commerce scraper example."""
    setup_logging()
    init_db()

    logger.info("=" * 60)
    logger.info("Starting Books to Scrape - Separate Tables Example")
    logger.info("=" * 60)

    # Create task in database
    with get_db_context() as db:
        task_repo = TaskRepository(db)
        task = task_repo.create(
            name="Books to Scrape - Full Catalog",
            target_url="https://books.toscrape.com/catalogue/page-1.html",
            task_type=TaskType.SCRAPE.value,
            config={
                "item_selector": "article.product_pod",
                "max_pages": MAX_PAGES,
                "page_delay": PAGE_DELAY,
            },
            selectors={
                "title": {"selector": "h3 a", "attribute": "title"},
                "price": "p.price_color",
                "availability": "p.availability",
                "rating": {"selector": "p.star-rating", "attribute": "class"},
                "image": {"selector": "div.image_container img", "attribute": "src"},
                "link": {"selector": "h3 a", "attribute": "href"},
            },
        )
        task_id = task.id
        task_repo.start_task(task_id, worker_id="example-worker")

    logger.info(f"Created task: {task_id}")

    # Create cleaning pipeline
    pipeline = create_cleaning_pipeline()

    # Create deduplicator
    deduplicator = Deduplicator(key_fields=["title", "price"])

    all_books = []
    pages_info = []
    total_raw = 0

    # Run scraping page by page
    with BrowserManager(headless=True) as browser:
        engine = ScrapingEngine(browser=browser)
        engine.start()

        base_url = "https://books.toscrape.com/catalogue/page-{}.html"

        for page_num in range(1, MAX_PAGES + 1):
            page_url = base_url.format(page_num)
            page_start = time.time()

            logger.info(f"Scraping page {page_num}/{MAX_PAGES}: {page_url}")

            # Configure scraping for this page
            scraping_config = ScrapingConfig(
                url=page_url,
                item_selector="article.product_pod",
                field_map={
                    "title": {"selector": "h3 a", "attribute": "title"},
                    "price": "p.price_color",
                    "availability": "p.availability",
                    "rating": {"selector": "p.star-rating", "attribute": "class"},
                    "image": {"selector": "div.image_container img", "attribute": "src"},
                    "link": {"selector": "h3 a", "attribute": "href"},
                },
                pagination_type=PaginationType.NEXT_BUTTON,  # Single page, no pagination needed
                max_pages=1,
                wait_for_selector="article.product_pod",
            )

            result = engine.scrape(scraping_config)
            page_duration = time.time() - page_start

            if result.success and result.data:
                raw_count = len(result.data)
                total_raw += raw_count

                # Clean data
                cleaned_data = pipeline.clean_batch(result.data)

                # Add page number to each item
                for item in cleaned_data:
                    item["_page_number"] = page_num

                # Store page info
                pages_info.append({
                    "page_number": page_num,
                    "page_url": page_url,
                    "items_count": len(cleaned_data),
                    "duration_seconds": round(page_duration, 2),
                    "success": True,
                })

                all_books.extend(cleaned_data)
                logger.info(f"  -> Found {len(cleaned_data)} books (took {page_duration:.1f}s)")
            else:
                logger.warning(f"  -> Failed to scrape page {page_num}")
                pages_info.append({
                    "page_number": page_num,
                    "page_url": page_url,
                    "items_count": 0,
                    "duration_seconds": round(page_duration, 2),
                    "success": False,
                    "error_message": str(result.errors) if result.errors else "Unknown error",
                })

            # Delay between pages
            if page_num < MAX_PAGES:
                time.sleep(PAGE_DELAY)

    # Deduplicate all books
    unique_books = deduplicator.deduplicate(all_books)
    logger.info(f"After deduplication: {len(unique_books)} unique books")

    # Save to database - SEPARATE TABLES
    with get_db_context() as db:
        page_repo = ScrapedPageRepository(db)
        book_repo = BookRepository(db)
        task_repo = TaskRepository(db)

        # Save pages to scraped_pages table
        logger.info("Saving pages to 'scraped_pages' table...")
        page_id_map = {}  # page_number -> page_id

        for page_info in pages_info:
            page = page_repo.create(
                task_id=task_id,
                page_number=page_info["page_number"],
                page_url=page_info["page_url"],
                items_count=page_info["items_count"],
                duration_seconds=page_info["duration_seconds"],
                success=page_info["success"],
                error_message=page_info.get("error_message"),
            )
            page_id_map[page_info["page_number"]] = page.id

        logger.info(f"  -> Saved {len(pages_info)} pages")

        # Save books to books table
        logger.info("Saving books to 'books' table...")
        books_to_insert = []

        for book_data in unique_books:
            page_num = book_data.get("_page_number", 1)
            page_id = page_id_map.get(page_num)

            books_to_insert.append({
                "task_id": task_id,
                "page_id": page_id,
                "title": book_data.get("title", "Unknown"),
                "price": book_data.get("price", 0.0),
                "price_currency": "GBP",
                "rating": book_data.get("rating", 0),
                "availability": book_data.get("availability"),
                "book_url": book_data.get("link"),
                "image_url": book_data.get("image"),
                "data_hash": book_data.get("_hash", ""),
            })

        # Bulk insert books
        book_repo.bulk_insert(books_to_insert)
        logger.info(f"  -> Saved {len(books_to_insert)} books")

        # Update task
        task_repo.complete_task(
            task_id,
            success=True,
            items_scraped=len(unique_books),
        )

    # Print summary
    logger.info("")
    logger.info("=" * 60)
    logger.info("SCRAPING COMPLETE - DATABASE SUMMARY")
    logger.info("=" * 60)

    # Query and display stats
    with get_db_context() as db:
        page_repo = ScrapedPageRepository(db)
        book_repo = BookRepository(db)

        pages = page_repo.get_by_task(task_id)
        books = book_repo.get_by_task(task_id)
        stats = book_repo.get_stats()

        logger.info(f"")
        logger.info(f"TABLE: scraped_pages")
        logger.info(f"  Total pages: {len(pages)}")
        for p in pages[:5]:
            logger.info(f"    Page {p.page_number}: {p.items_count} items ({p.duration_seconds}s)")
        if len(pages) > 5:
            logger.info(f"    ... and {len(pages) - 5} more pages")

        logger.info(f"")
        logger.info(f"TABLE: books")
        logger.info(f"  Total books: {stats['total_books']}")
        logger.info(f"  Average price: {stats['avg_price']:.2f} GBP")
        logger.info(f"  Average rating: {stats['avg_rating']:.1f} stars")
        logger.info(f"  Price range: {stats['min_price']:.2f} - {stats['max_price']:.2f} GBP")

        logger.info(f"")
        logger.info(f"Sample books:")
        for b in books[:5]:
            stars = "*" * b.rating + "." * (5 - b.rating)
            logger.info(f"  [{stars}] {b.title[:40]}... - {b.price:.2f} GBP")

    logger.info("")
    logger.info("=" * 60)

    return unique_books


if __name__ == "__main__":
    items = asyncio.run(run_scraper())
    print(f"\nSuccessfully scraped {len(items)} books into separate tables!")
    print("Tables created: scraped_pages, books")
