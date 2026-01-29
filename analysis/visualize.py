"""Database visualization and analysis for Books Scraper.

This module generates charts and reports from the scraped book data.
It creates visual representations of:
- Price distribution
- Rating distribution
- Books per page
- Price vs Rating correlation
- Top/Bottom priced books
- Scraping performance metrics

Usage:
    python -m analysis.visualize
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for saving files

import numpy as np
from collections import Counter
from datetime import datetime

from src.database.connection import get_db_context
from src.database.repository import BookRepository, ScrapedPageRepository, TaskRepository

# Output directory for charts
OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


def get_data():
    """Fetch all data from database."""
    with get_db_context() as db:
        book_repo = BookRepository(db)
        page_repo = ScrapedPageRepository(db)
        task_repo = TaskRepository(db)

        books = book_repo.get_all(limit=1000)
        pages = page_repo.get_all(limit=100)
        tasks = task_repo.get_all(limit=100)
        stats = book_repo.get_stats()

        # Convert to dicts for easier manipulation
        books_data = [b.to_dict() for b in books]
        pages_data = [p.to_dict() for p in pages]

    return books_data, pages_data, stats


def plot_price_distribution(books, output_path):
    """Create price distribution histogram."""
    prices = [b['price'] for b in books if b['price']]

    fig, ax = plt.subplots(figsize=(12, 6))

    # Histogram
    n, bins, patches = ax.hist(prices, bins=20, color='#3498db', edgecolor='white', alpha=0.7)

    # Add mean and median lines
    mean_price = np.mean(prices)
    median_price = np.median(prices)

    ax.axvline(mean_price, color='red', linestyle='--', linewidth=2, label=f'Mean: £{mean_price:.2f}')
    ax.axvline(median_price, color='green', linestyle='--', linewidth=2, label=f'Median: £{median_price:.2f}')

    ax.set_xlabel('Price (GBP)', fontsize=12)
    ax.set_ylabel('Number of Books', fontsize=12)
    ax.set_title('Book Price Distribution', fontsize=14, fontweight='bold')
    ax.legend(loc='upper right')
    ax.grid(axis='y', alpha=0.3)

    # Add stats text
    stats_text = f'Total Books: {len(prices)}\nMin: £{min(prices):.2f}\nMax: £{max(prices):.2f}'
    ax.text(0.02, 0.98, stats_text, transform=ax.transAxes, fontsize=10,
            verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  Saved: {output_path}")


def plot_rating_distribution(books, output_path):
    """Create rating distribution bar chart."""
    ratings = [b['rating'] for b in books if b['rating'] is not None]
    rating_counts = Counter(ratings)

    fig, ax = plt.subplots(figsize=(10, 6))

    # Bar chart
    stars = ['1 Star', '2 Stars', '3 Stars', '4 Stars', '5 Stars']
    counts = [rating_counts.get(i, 0) for i in range(1, 6)]
    colors = ['#e74c3c', '#e67e22', '#f1c40f', '#2ecc71', '#27ae60']

    bars = ax.bar(stars, counts, color=colors, edgecolor='white', linewidth=2)

    # Add value labels on bars
    for bar, count in zip(bars, counts):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{count}\n({count/len(ratings)*100:.1f}%)',
                ha='center', va='bottom', fontsize=10)

    ax.set_xlabel('Rating', fontsize=12)
    ax.set_ylabel('Number of Books', fontsize=12)
    ax.set_title('Book Rating Distribution', fontsize=14, fontweight='bold')
    ax.grid(axis='y', alpha=0.3)

    # Add average rating
    avg_rating = np.mean(ratings)
    ax.axhline(y=len(ratings)/5, color='gray', linestyle='--', alpha=0.5)
    ax.text(0.98, 0.98, f'Average Rating: {avg_rating:.2f} stars',
            transform=ax.transAxes, fontsize=11, ha='right', va='top',
            bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.8))

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  Saved: {output_path}")


def plot_price_vs_rating(books, output_path):
    """Create price vs rating scatter plot."""
    prices = [b['price'] for b in books if b['price'] and b['rating']]
    ratings = [b['rating'] for b in books if b['price'] and b['rating']]

    fig, ax = plt.subplots(figsize=(12, 8))

    # Scatter plot with jitter for better visibility
    jitter_ratings = [r + np.random.uniform(-0.2, 0.2) for r in ratings]

    scatter = ax.scatter(jitter_ratings, prices, c=ratings, cmap='RdYlGn',
                         alpha=0.6, s=50, edgecolors='white', linewidth=0.5)

    # Add colorbar
    cbar = plt.colorbar(scatter, ax=ax)
    cbar.set_label('Rating', fontsize=11)

    # Calculate average price per rating
    avg_prices = {}
    for r in range(1, 6):
        r_prices = [b['price'] for b in books if b['rating'] == r and b['price']]
        if r_prices:
            avg_prices[r] = np.mean(r_prices)

    # Plot average line
    if avg_prices:
        ax.plot(list(avg_prices.keys()), list(avg_prices.values()),
                'b-o', linewidth=2, markersize=8, label='Average Price per Rating')

    ax.set_xlabel('Rating (Stars)', fontsize=12)
    ax.set_ylabel('Price (GBP)', fontsize=12)
    ax.set_title('Price vs Rating Analysis', fontsize=14, fontweight='bold')
    ax.set_xticks([1, 2, 3, 4, 5])
    ax.set_xticklabels(['1 Star', '2 Stars', '3 Stars', '4 Stars', '5 Stars'])
    ax.grid(True, alpha=0.3)
    ax.legend(loc='upper left')

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  Saved: {output_path}")


def plot_books_per_page(pages, output_path):
    """Create books per page bar chart."""
    fig, ax = plt.subplots(figsize=(14, 6))

    page_nums = [p['page_number'] for p in pages]
    items_counts = [p['items_count'] for p in pages]
    durations = [p['duration_seconds'] or 0 for p in pages]

    # Create bar chart
    bars = ax.bar(page_nums, items_counts, color='#9b59b6', edgecolor='white', alpha=0.8)

    ax.set_xlabel('Page Number', fontsize=12)
    ax.set_ylabel('Number of Books', fontsize=12)
    ax.set_title('Books Scraped per Page', fontsize=14, fontweight='bold')
    ax.set_xticks(page_nums)
    ax.grid(axis='y', alpha=0.3)

    # Add secondary axis for duration
    ax2 = ax.twinx()
    ax2.plot(page_nums, durations, 'r-o', linewidth=2, markersize=6, label='Scrape Duration')
    ax2.set_ylabel('Duration (seconds)', color='red', fontsize=12)
    ax2.tick_params(axis='y', labelcolor='red')

    # Add legend
    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines2, labels2, loc='upper right')

    # Add totals
    total_books = sum(items_counts)
    total_duration = sum(durations)
    ax.text(0.02, 0.98, f'Total: {total_books} books in {total_duration:.1f}s',
            transform=ax.transAxes, fontsize=11, va='top',
            bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.8))

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  Saved: {output_path}")


def plot_top_bottom_books(books, output_path):
    """Create top and bottom priced books horizontal bar chart."""
    sorted_books = sorted(books, key=lambda x: x['price'] or 0, reverse=True)

    top_5 = sorted_books[:5]
    bottom_5 = sorted_books[-5:][::-1]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

    # Top 5 most expensive
    titles_top = [b['title'][:30] + '...' if len(b['title']) > 30 else b['title'] for b in top_5]
    prices_top = [b['price'] for b in top_5]
    ratings_top = [b['rating'] for b in top_5]

    colors_top = ['#27ae60' if r >= 4 else '#f1c40f' if r >= 3 else '#e74c3c' for r in ratings_top]
    bars1 = ax1.barh(titles_top, prices_top, color=colors_top, edgecolor='white')
    ax1.set_xlabel('Price (GBP)', fontsize=12)
    ax1.set_title('Top 5 Most Expensive Books', fontsize=14, fontweight='bold')
    ax1.invert_yaxis()

    # Add price labels
    for bar, price, rating in zip(bars1, prices_top, ratings_top):
        ax1.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height()/2,
                f'£{price:.2f} ({rating}★)', va='center', fontsize=10)

    # Bottom 5 cheapest
    titles_bottom = [b['title'][:30] + '...' if len(b['title']) > 30 else b['title'] for b in bottom_5]
    prices_bottom = [b['price'] for b in bottom_5]
    ratings_bottom = [b['rating'] for b in bottom_5]

    colors_bottom = ['#27ae60' if r >= 4 else '#f1c40f' if r >= 3 else '#e74c3c' for r in ratings_bottom]
    bars2 = ax2.barh(titles_bottom, prices_bottom, color=colors_bottom, edgecolor='white')
    ax2.set_xlabel('Price (GBP)', fontsize=12)
    ax2.set_title('Top 5 Cheapest Books', fontsize=14, fontweight='bold')
    ax2.invert_yaxis()

    # Add price labels
    for bar, price, rating in zip(bars2, prices_bottom, ratings_bottom):
        ax2.text(bar.get_width() + 0.3, bar.get_y() + bar.get_height()/2,
                f'£{price:.2f} ({rating}★)', va='center', fontsize=10)

    # Add legend
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor='#27ae60', label='4-5 Stars'),
        Patch(facecolor='#f1c40f', label='3 Stars'),
        Patch(facecolor='#e74c3c', label='1-2 Stars')
    ]
    fig.legend(handles=legend_elements, loc='lower center', ncol=3, fontsize=10)

    plt.tight_layout()
    plt.subplots_adjust(bottom=0.15)
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  Saved: {output_path}")


def plot_summary_dashboard(books, pages, stats, output_path):
    """Create a summary dashboard with multiple metrics."""
    fig = plt.figure(figsize=(16, 12))

    # Create grid
    gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3)

    # 1. Key Metrics (top row, span 3 columns)
    ax_metrics = fig.add_subplot(gs[0, :])
    ax_metrics.axis('off')

    metrics_text = f"""
    📚 BOOKS DATABASE ANALYSIS DASHBOARD
    ═══════════════════════════════════════════════════════════════════

    Total Books: {stats['total_books']}          Total Pages: {len(pages)}
    Average Price: £{stats['avg_price']:.2f}       Price Range: £{stats['min_price']:.2f} - £{stats['max_price']:.2f}
    Average Rating: {stats['avg_rating']:.1f} ★

    Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    """
    ax_metrics.text(0.5, 0.5, metrics_text, transform=ax_metrics.transAxes,
                   fontsize=14, ha='center', va='center', family='monospace',
                   bbox=dict(boxstyle='round', facecolor='#ecf0f1', alpha=0.8))

    # 2. Price Distribution (mini)
    ax_price = fig.add_subplot(gs[1, 0])
    prices = [b['price'] for b in books if b['price']]
    ax_price.hist(prices, bins=15, color='#3498db', edgecolor='white', alpha=0.7)
    ax_price.set_title('Price Distribution', fontsize=11, fontweight='bold')
    ax_price.set_xlabel('Price (GBP)')
    ax_price.set_ylabel('Count')

    # 3. Rating Distribution (mini)
    ax_rating = fig.add_subplot(gs[1, 1])
    ratings = [b['rating'] for b in books if b['rating']]
    rating_counts = Counter(ratings)
    colors = ['#e74c3c', '#e67e22', '#f1c40f', '#2ecc71', '#27ae60']
    ax_rating.bar(range(1, 6), [rating_counts.get(i, 0) for i in range(1, 6)], color=colors)
    ax_rating.set_title('Rating Distribution', fontsize=11, fontweight='bold')
    ax_rating.set_xlabel('Stars')
    ax_rating.set_ylabel('Count')
    ax_rating.set_xticks(range(1, 6))

    # 4. Price by Rating Box Plot
    ax_box = fig.add_subplot(gs[1, 2])
    price_by_rating = [[b['price'] for b in books if b['rating'] == r and b['price']] for r in range(1, 6)]
    bp = ax_box.boxplot(price_by_rating, patch_artist=True)
    for patch, color in zip(bp['boxes'], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)
    ax_box.set_title('Price by Rating', fontsize=11, fontweight='bold')
    ax_box.set_xlabel('Rating (Stars)')
    ax_box.set_ylabel('Price (GBP)')
    ax_box.set_xticklabels(['1', '2', '3', '4', '5'])

    # 5. Scraping Performance
    ax_perf = fig.add_subplot(gs[2, 0])
    page_nums = [p['page_number'] for p in pages]
    durations = [p['duration_seconds'] or 0 for p in pages]
    ax_perf.plot(page_nums, durations, 'b-o', linewidth=2, markersize=4)
    ax_perf.fill_between(page_nums, durations, alpha=0.3)
    ax_perf.set_title('Scraping Duration per Page', fontsize=11, fontweight='bold')
    ax_perf.set_xlabel('Page')
    ax_perf.set_ylabel('Duration (s)')
    ax_perf.grid(True, alpha=0.3)

    # 6. Availability Pie Chart
    ax_avail = fig.add_subplot(gs[2, 1])
    avail_counts = Counter([b.get('availability', 'Unknown') for b in books])
    in_stock = sum(v for k, v in avail_counts.items() if 'In stock' in str(k))
    out_stock = sum(v for k, v in avail_counts.items() if 'In stock' not in str(k))
    ax_avail.pie([in_stock, out_stock], labels=['In Stock', 'Out of Stock'],
                 colors=['#2ecc71', '#e74c3c'], autopct='%1.1f%%', startangle=90)
    ax_avail.set_title('Stock Availability', fontsize=11, fontweight='bold')

    # 7. Top Books Table
    ax_table = fig.add_subplot(gs[2, 2])
    ax_table.axis('off')
    sorted_books = sorted(books, key=lambda x: x.get('rating', 0), reverse=True)[:5]
    table_data = [[b['title'][:25] + '...', f"£{b['price']:.2f}", f"{b['rating']}★"]
                  for b in sorted_books]
    table = ax_table.table(cellText=table_data,
                          colLabels=['Title', 'Price', 'Rating'],
                          loc='center', cellLoc='left')
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 1.5)
    ax_table.set_title('Top Rated Books', fontsize=11, fontweight='bold', y=0.9)

    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"  Saved: {output_path}")


def generate_html_report(books, pages, stats, output_path):
    """Generate an HTML report with all statistics."""

    # Calculate additional stats
    ratings = [b['rating'] for b in books if b['rating']]
    prices = [b['price'] for b in books if b['price']]

    rating_dist = Counter(ratings)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Books Scraper - Database Analysis Report</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Segoe UI', Tahoma, sans-serif; background: #f5f6fa; color: #2c3e50; line-height: 1.6; }}
        .container {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 40px; border-radius: 10px; margin-bottom: 30px; text-align: center; }}
        .header h1 {{ font-size: 2.5em; margin-bottom: 10px; }}
        .header p {{ opacity: 0.9; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 30px; }}
        .card {{ background: white; border-radius: 10px; padding: 25px; box-shadow: 0 2px 15px rgba(0,0,0,0.1); }}
        .card h3 {{ color: #667eea; margin-bottom: 15px; font-size: 1.1em; text-transform: uppercase; letter-spacing: 1px; }}
        .metric {{ font-size: 2.5em; font-weight: bold; color: #2c3e50; }}
        .metric-label {{ color: #7f8c8d; font-size: 0.9em; }}
        .chart-container {{ margin-bottom: 30px; }}
        .chart-container img {{ width: 100%; border-radius: 10px; box-shadow: 0 2px 15px rgba(0,0,0,0.1); }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ecf0f1; }}
        th {{ background: #667eea; color: white; }}
        tr:hover {{ background: #f8f9fa; }}
        .rating {{ color: #f1c40f; }}
        .progress-bar {{ height: 10px; background: #ecf0f1; border-radius: 5px; overflow: hidden; margin: 5px 0; }}
        .progress {{ height: 100%; border-radius: 5px; }}
        .star-1 {{ background: #e74c3c; }}
        .star-2 {{ background: #e67e22; }}
        .star-3 {{ background: #f1c40f; }}
        .star-4 {{ background: #2ecc71; }}
        .star-5 {{ background: #27ae60; }}
        footer {{ text-align: center; padding: 20px; color: #7f8c8d; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📚 Books Database Analysis</h1>
            <p>Comprehensive report from scraped book data</p>
            <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>

        <div class="grid">
            <div class="card">
                <h3>📖 Total Books</h3>
                <div class="metric">{stats['total_books']}</div>
                <div class="metric-label">books in database</div>
            </div>
            <div class="card">
                <h3>📄 Pages Scraped</h3>
                <div class="metric">{len(pages)}</div>
                <div class="metric-label">pages processed</div>
            </div>
            <div class="card">
                <h3>💰 Average Price</h3>
                <div class="metric">£{stats['avg_price']:.2f}</div>
                <div class="metric-label">per book</div>
            </div>
            <div class="card">
                <h3>⭐ Average Rating</h3>
                <div class="metric">{stats['avg_rating']:.1f}</div>
                <div class="metric-label">out of 5 stars</div>
            </div>
        </div>

        <div class="grid">
            <div class="card">
                <h3>💵 Price Range</h3>
                <p><strong>Minimum:</strong> £{stats['min_price']:.2f}</p>
                <p><strong>Maximum:</strong> £{stats['max_price']:.2f}</p>
                <p><strong>Median:</strong> £{np.median(prices):.2f}</p>
            </div>
            <div class="card">
                <h3>⭐ Rating Distribution</h3>
                {"".join([f'''
                <div style="margin-bottom: 8px;">
                    <span>{i} Star{'s' if i > 1 else ''}: {rating_dist.get(i, 0)} ({rating_dist.get(i, 0)/len(ratings)*100:.1f}%)</span>
                    <div class="progress-bar">
                        <div class="progress star-{i}" style="width: {rating_dist.get(i, 0)/len(ratings)*100}%"></div>
                    </div>
                </div>''' for i in range(1, 6)])}
            </div>
        </div>

        <div class="card chart-container">
            <h3>📊 Dashboard Overview</h3>
            <img src="dashboard.png" alt="Dashboard">
        </div>

        <div class="grid">
            <div class="card chart-container">
                <h3>💰 Price Distribution</h3>
                <img src="price_distribution.png" alt="Price Distribution">
            </div>
            <div class="card chart-container">
                <h3>⭐ Rating Distribution</h3>
                <img src="rating_distribution.png" alt="Rating Distribution">
            </div>
        </div>

        <div class="grid">
            <div class="card chart-container">
                <h3>📈 Price vs Rating</h3>
                <img src="price_vs_rating.png" alt="Price vs Rating">
            </div>
            <div class="card chart-container">
                <h3>📄 Books per Page</h3>
                <img src="books_per_page.png" alt="Books per Page">
            </div>
        </div>

        <div class="card chart-container">
            <h3>🏆 Top & Bottom Priced Books</h3>
            <img src="top_bottom_books.png" alt="Top Bottom Books">
        </div>

        <div class="card">
            <h3>📋 Sample Books Data</h3>
            <table>
                <thead>
                    <tr>
                        <th>Title</th>
                        <th>Price</th>
                        <th>Rating</th>
                        <th>Availability</th>
                    </tr>
                </thead>
                <tbody>
                    {"".join([f'''
                    <tr>
                        <td>{b['title'][:50]}{'...' if len(b['title']) > 50 else ''}</td>
                        <td>£{b['price']:.2f}</td>
                        <td class="rating">{"★" * b['rating']}{"☆" * (5-b['rating'])}</td>
                        <td>{b.get('availability', 'N/A')}</td>
                    </tr>''' for b in sorted(books, key=lambda x: x.get('price', 0), reverse=True)[:20]])}
                </tbody>
            </table>
        </div>

        <div class="card">
            <h3>📄 Scraping Performance</h3>
            <table>
                <thead>
                    <tr>
                        <th>Page</th>
                        <th>URL</th>
                        <th>Items</th>
                        <th>Duration</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
                    {"".join([f'''
                    <tr>
                        <td>Page {p['page_number']}</td>
                        <td><a href="{p['page_url']}" target="_blank">View</a></td>
                        <td>{p['items_count']}</td>
                        <td>{p['duration_seconds']:.2f}s</td>
                        <td>{"✅ Success" if p['success'] else "❌ Failed"}</td>
                    </tr>''' for p in pages[:10]])}
                </tbody>
            </table>
        </div>

        <footer>
            <p>Generated by RPAFlow - Books Scraper Analysis Module</p>
            <p>Data source: books.toscrape.com</p>
        </footer>
    </div>
</body>
</html>
"""

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f"  Saved: {output_path}")


def main():
    """Generate all visualizations and reports."""
    print("=" * 60)
    print("BOOKS DATABASE ANALYSIS & VISUALIZATION")
    print("=" * 60)
    print()

    print("Fetching data from database...")
    books, pages, stats = get_data()
    print(f"  Found {len(books)} books and {len(pages)} pages")
    print()

    print("Generating visualizations...")

    # Generate all charts
    plot_price_distribution(books, OUTPUT_DIR / "price_distribution.png")
    plot_rating_distribution(books, OUTPUT_DIR / "rating_distribution.png")
    plot_price_vs_rating(books, OUTPUT_DIR / "price_vs_rating.png")
    plot_books_per_page(pages, OUTPUT_DIR / "books_per_page.png")
    plot_top_bottom_books(books, OUTPUT_DIR / "top_bottom_books.png")
    plot_summary_dashboard(books, pages, stats, OUTPUT_DIR / "dashboard.png")

    print()
    print("Generating HTML report...")
    generate_html_report(books, pages, stats, OUTPUT_DIR / "report.html")

    print()
    print("=" * 60)
    print("ANALYSIS COMPLETE!")
    print("=" * 60)
    print(f"\nOutput directory: {OUTPUT_DIR}")
    print("\nGenerated files:")
    for f in OUTPUT_DIR.glob("*"):
        print(f"  - {f.name}")


if __name__ == "__main__":
    main()
