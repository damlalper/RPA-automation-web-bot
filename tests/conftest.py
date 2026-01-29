"""Pytest configuration and fixtures."""

import os
import sys
from pathlib import Path

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Set test environment
os.environ["APP_ENV"] = "development"
os.environ["DEBUG"] = "true"
os.environ["DATABASE_URL"] = "sqlite:///./test_data/test.db"


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Setup test environment."""
    # Create test data directory
    test_data_dir = project_root / "test_data"
    test_data_dir.mkdir(exist_ok=True)

    yield

    # Cleanup
    import shutil
    if test_data_dir.exists():
        shutil.rmtree(test_data_dir)


@pytest.fixture
def sample_scraped_data():
    """Sample scraped data for testing."""
    return [
        {
            "title": "Book One",
            "price": "£19.99",
            "availability": "In stock",
            "rating": "star-rating Three",
        },
        {
            "title": "Book Two",
            "price": "£24.99",
            "availability": "In stock",
            "rating": "star-rating Five",
        },
        {
            "title": "Book Three",
            "price": "£9.99",
            "availability": "Out of stock",
            "rating": "star-rating One",
        },
    ]


@pytest.fixture
def sample_task_config():
    """Sample task configuration for testing."""
    return {
        "name": "Test Scraping Task",
        "target_url": "https://books.toscrape.com",
        "task_type": "scrape",
        "config": {
            "item_selector": "article.product_pod",
            "max_pages": 1,
        },
        "selectors": {
            "title": {"selector": "h3 a", "attribute": "title"},
            "price": "p.price_color",
        },
    }
