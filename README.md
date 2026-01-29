# RPAFlow - Enterprise RPA Automation Platform

Selenium tabanlı, proxy-aware, ölçeklenebilir RPA (Robotik Süreç Otomasyonu) platformu.

## 🚀 Özellikler

- **Selenium Automation Engine** - Web otomasyonu, form doldurma, navigasyon
- **Proxy & IP Rotation** - Proxy pool yönetimi, rotasyon stratejileri
- **Web Scraping** - DOM parsing, pagination, veri çıkarma
- **Data Cleaning Pipeline** - Normalizasyon, temizleme, deduplication
- **Database Layer** - SQLite/PostgreSQL, ORM, batch operations
- **Worker Pool** - Paralel task yürütme, retry logic
- **FastAPI Backend** - REST API, WebSocket desteği
- **React Dashboard** - Gerçek zamanlı monitoring
- **Docker Support** - Production-ready deployment

## 📦 Tech Stack

| Katman | Teknoloji |
|--------|-----------|
| Backend | Python 3.11+ |
| Automation | Selenium, WebDriver Manager |
| Scraping | BeautifulSoup, lxml |
| API | FastAPI, Uvicorn |
| Database | SQLAlchemy, SQLite/PostgreSQL |
| Frontend | React 18, TypeScript, Vite |
| Styling | TailwindCSS |
| Charts | Recharts |
| Logging | Loguru |
| Scheduling | APScheduler |

## 🛠️ Kurulum

### 1. Repository'yi klonla
```bash
git clone <repo-url>
cd rpa-automation-web-bot
```

### 2. Python bağımlılıklarını yükle
```bash
# Virtual environment oluştur
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Bağımlılıkları yükle
pip install -r requirements.txt
```

### 3. Environment dosyasını oluştur
```bash
cp .env.example .env
# .env dosyasını düzenle
```

### 4. Veritabanını başlat
```bash
python -c "from src.database.connection import init_db; init_db()"
```

### 5. API'yi çalıştır
```bash
uvicorn src.api.main:app --reload --port 8000
```

### 6. Frontend'i çalıştır (opsiyonel)
```bash
cd frontend
npm install
npm run dev
```

## 🐳 Docker ile Çalıştırma

```bash
cd docker
docker-compose up -d
```

Servisler:
- API: http://localhost:8000
- PostgreSQL: localhost:5432
- Redis: localhost:6379

## 📝 Kullanım

### API Endpoints

```bash
# Health check
curl http://localhost:8000/api/health

# Task oluştur
curl -X POST http://localhost:8000/api/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Scraping Task",
    "target_url": "https://example.com",
    "task_type": "scrape"
  }'

# Taskları listele
curl http://localhost:8000/api/tasks

# Metrikleri görüntüle
curl http://localhost:8000/api/metrics/summary
```

### Örnek Scraper

```python
from src.automation.browser import BrowserManager
from src.scraping.engine import ScrapingConfig, ScrapingEngine
from src.scraping.pagination import PaginationType

# Scraping config
config = ScrapingConfig(
    url="https://books.toscrape.com",
    item_selector="article.product_pod",
    field_map={
        "title": {"selector": "h3 a", "attribute": "title"},
        "price": "p.price_color",
    },
    pagination_type=PaginationType.NEXT_BUTTON,
    pagination_selector="li.next a",
    max_pages=3,
)

# Scraping çalıştır
with BrowserManager(headless=True) as browser:
    engine = ScrapingEngine(browser=browser)
    result = engine.scrape(config)
    print(f"Scraped {len(result.data)} items")
```

### E-commerce Örneği

```bash
python -m examples.ecommerce_scraper.run
```

## 🧪 Testler

```bash
# Tüm testleri çalıştır
pytest

# Sadece unit testler
pytest tests/unit/

# Coverage ile
pytest --cov=src --cov-report=html
```

## 📂 Proje Yapısı

```
rpa-automation-web-bot/
├── src/
│   ├── api/              # FastAPI backend
│   ├── automation/       # Selenium engine
│   ├── cleaning/         # Data cleaning
│   ├── core/             # Config, orchestrator
│   ├── database/         # Models, repository
│   ├── monitoring/       # Logging, metrics
│   ├── proxy/            # Proxy management
│   ├── scraping/         # Scraping engine
│   └── workers/          # Worker pool
├── frontend/             # React dashboard
├── examples/             # Örnek scraperlar
├── tests/                # Test suite
├── docker/               # Docker config
└── requirements.txt
```

## 📊 Dashboard

Dashboard özellikleri:
- Real-time task monitoring
- Performance metrikleri
- Proxy health status
- Task yönetimi (create, cancel, retry)

## ⚙️ Konfigürasyon

Önemli environment değişkenleri:

| Değişken | Varsayılan | Açıklama |
|----------|------------|----------|
| `DATABASE_URL` | `sqlite:///./data/rpaflow.db` | DB bağlantı URL |
| `SELENIUM_HEADLESS` | `true` | Headless mode |
| `PROXY_ENABLED` | `false` | Proxy rotasyonu |
| `WORKER_POOL_SIZE` | `5` | Worker sayısı |
| `LOG_LEVEL` | `INFO` | Log seviyesi |

## 🔒 Güvenlik

- `.env` dosyasını asla commit etmeyin
- Production'da güçlü veritabanı şifresi kullanın
- CORS ayarlarını production için kısıtlayın
- Rate limiting uygulayın

## 📄 Lisans

MIT License

## 🤝 Katkıda Bulunma

1. Fork yapın
2. Feature branch oluşturun (`git checkout -b feature/amazing`)
3. Değişiklikleri commit edin (`git commit -m 'Add amazing feature'`)
4. Branch'i push edin (`git push origin feature/amazing`)
5. Pull Request açın


