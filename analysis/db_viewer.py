"""Database Viewer - Shows actual database tables and their contents.

This script displays the raw database structure and data,
allowing you to see exactly what's stored in each table.

Usage:
    python -m analysis.db_viewer
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tabulate import tabulate
from src.database.connection import get_db_context, get_engine
from src.database.models import Base, Task, ScrapedPage, Book, ScrapedData, ProxyStatus, BotMetrics
from sqlalchemy import inspect, text


def print_separator(title=""):
    """Print a visual separator."""
    if title:
        print(f"\n{'='*70}")
        print(f"  {title}")
        print(f"{'='*70}")
    else:
        print("-" * 70)


def show_database_info():
    """Show database file info and tables."""
    engine = get_engine()
    inspector = inspect(engine)

    print_separator("DATABASE INFO")
    print(f"Database URL: {engine.url}")
    print(f"\nTables in database:")

    tables = inspector.get_table_names()
    for table in tables:
        columns = inspector.get_columns(table)
        print(f"\n  [{table}]")
        for col in columns:
            nullable = "NULL" if col['nullable'] else "NOT NULL"
            print(f"    - {col['name']}: {col['type']} {nullable}")


def show_table_counts():
    """Show record counts for all tables."""
    print_separator("TABLE RECORD COUNTS")

    with get_db_context() as db:
        tables = [
            ("tasks", Task),
            ("scraped_pages", ScrapedPage),
            ("books", Book),
            ("scraped_data", ScrapedData),
            ("proxy_status", ProxyStatus),
            ("bot_metrics", BotMetrics),
        ]

        data = []
        for name, model in tables:
            try:
                count = db.query(model).count()
                data.append([name, count])
            except Exception as e:
                data.append([name, f"Error: {e}"])

        print(tabulate(data, headers=["Table", "Records"], tablefmt="grid"))


def show_tasks_table():
    """Show tasks table content."""
    print_separator("TABLE: tasks")

    with get_db_context() as db:
        tasks = db.query(Task).order_by(Task.created_at.desc()).limit(10).all()

        if not tasks:
            print("  (empty)")
            return

        data = []
        for t in tasks:
            data.append([
                t.id[:8] + "...",
                t.name[:30],
                t.status,
                t.task_type,
                t.items_scraped,
                str(t.created_at)[:19] if t.created_at else "-"
            ])

        print(tabulate(data,
                      headers=["ID", "Name", "Status", "Type", "Items", "Created"],
                      tablefmt="grid"))
        print(f"\n  Showing {len(tasks)} of {db.query(Task).count()} total records")


def show_pages_table():
    """Show scraped_pages table content."""
    print_separator("TABLE: scraped_pages")

    with get_db_context() as db:
        pages = db.query(ScrapedPage).order_by(ScrapedPage.page_number).limit(25).all()

        if not pages:
            print("  (empty)")
            return

        data = []
        for p in pages:
            data.append([
                p.id[:8] + "...",
                p.page_number,
                p.page_url[-30:],
                p.items_count,
                f"{p.duration_seconds:.2f}s" if p.duration_seconds else "-",
                "Yes" if p.success else "No"
            ])

        print(tabulate(data,
                      headers=["ID", "Page#", "URL (last 30 chars)", "Items", "Duration", "Success"],
                      tablefmt="grid"))
        print(f"\n  Showing {len(pages)} of {db.query(ScrapedPage).count()} total records")


def show_books_table():
    """Show books table content."""
    print_separator("TABLE: books")

    with get_db_context() as db:
        books = db.query(Book).order_by(Book.price.desc()).limit(20).all()

        if not books:
            print("  (empty)")
            return

        data = []
        for b in books:
            stars = "*" * b.rating + "." * (5 - b.rating)
            data.append([
                b.id[:8] + "...",
                b.title[:35] + ("..." if len(b.title) > 35 else ""),
                f"{b.price:.2f}",
                b.price_currency,
                stars,
                b.availability[:15] if b.availability else "-"
            ])

        print(tabulate(data,
                      headers=["ID", "Title", "Price", "Currency", "Rating", "Availability"],
                      tablefmt="grid"))

        total = db.query(Book).count()
        print(f"\n  Showing top 20 by price of {total} total records")


def show_books_sample_by_rating():
    """Show books grouped by rating."""
    print_separator("BOOKS BY RATING")

    with get_db_context() as db:
        for rating in range(5, 0, -1):
            books = db.query(Book).filter(Book.rating == rating).limit(3).all()
            star_display = "*" * rating + "." * (5 - rating)
            count = db.query(Book).filter(Book.rating == rating).count()

            print(f"\n  {star_display} ({count} books)")
            for b in books:
                print(f"    - {b.title[:50]} | {b.price:.2f} GBP")


def show_database_statistics():
    """Show database statistics."""
    print_separator("DATABASE STATISTICS")

    with get_db_context() as db:
        from sqlalchemy import func

        # Book stats
        book_stats = db.query(
            func.count(Book.id).label('total'),
            func.avg(Book.price).label('avg_price'),
            func.min(Book.price).label('min_price'),
            func.max(Book.price).label('max_price'),
            func.avg(Book.rating).label('avg_rating')
        ).first()

        print("\n  BOOKS:")
        print(f"    Total Records: {book_stats.total}")
        print(f"    Price Range: {book_stats.min_price:.2f} - {book_stats.max_price:.2f} GBP")
        print(f"    Average Price: {book_stats.avg_price:.2f} GBP")
        print(f"    Average Rating: {book_stats.avg_rating:.1f} stars")

        # Page stats
        page_stats = db.query(
            func.count(ScrapedPage.id).label('total'),
            func.sum(ScrapedPage.items_count).label('total_items'),
            func.avg(ScrapedPage.duration_seconds).label('avg_duration')
        ).first()

        print("\n  PAGES:")
        print(f"    Total Pages: {page_stats.total}")
        print(f"    Total Items Scraped: {page_stats.total_items}")
        print(f"    Average Scrape Duration: {page_stats.avg_duration:.2f}s per page")

        # Task stats
        task_count = db.query(Task).count()
        success_count = db.query(Task).filter(Task.status == 'success').count()

        print("\n  TASKS:")
        print(f"    Total Tasks: {task_count}")
        print(f"    Successful: {success_count}")


def export_to_csv():
    """Export tables to CSV files."""
    import csv

    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)

    print_separator("EXPORTING TO CSV")

    with get_db_context() as db:
        # Export books
        books = db.query(Book).all()
        books_file = output_dir / "books_table.csv"
        with open(books_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['id', 'title', 'price', 'currency', 'rating', 'availability', 'book_url', 'image_url'])
            for b in books:
                writer.writerow([b.id, b.title, b.price, b.price_currency, b.rating, b.availability, b.book_url, b.image_url])
        print(f"  Exported {len(books)} books to: {books_file}")

        # Export pages
        pages = db.query(ScrapedPage).all()
        pages_file = output_dir / "pages_table.csv"
        with open(pages_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['id', 'page_number', 'page_url', 'items_count', 'duration_seconds', 'success', 'scraped_at'])
            for p in pages:
                writer.writerow([p.id, p.page_number, p.page_url, p.items_count, p.duration_seconds, p.success, p.scraped_at])
        print(f"  Exported {len(pages)} pages to: {pages_file}")

        # Export tasks
        tasks = db.query(Task).all()
        tasks_file = output_dir / "tasks_table.csv"
        with open(tasks_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['id', 'name', 'status', 'task_type', 'target_url', 'items_scraped', 'created_at'])
            for t in tasks:
                writer.writerow([t.id, t.name, t.status, t.task_type, t.target_url, t.items_scraped, t.created_at])
        print(f"  Exported {len(tasks)} tasks to: {tasks_file}")


def main():
    """Main function to display all database information."""
    print("\n" + "=" * 70)
    print("       RPAFLOW DATABASE VIEWER")
    print("       Showing actual database tables and contents")
    print("=" * 70)

    # Show all info
    show_database_info()
    show_table_counts()
    show_tasks_table()
    show_pages_table()
    show_books_table()
    show_books_sample_by_rating()
    show_database_statistics()
    export_to_csv()

    print_separator("DONE")
    print("\nCSV files exported to: analysis/output/")
    print("You can open these in Excel or any spreadsheet application.\n")


if __name__ == "__main__":
    main()
