# 🤖 Enterprise RPA Automation Suite  
**Web Automation, Scraping & Proxy-Aware Bot Framework**

Gerçek dünyadaki web süreçlerini otomatikleştiren, ölçeklenebilir ve test edilebilir bir **RPA platformu**.

---

## 🧠 Proje Amacı

Bu sistem şunları sağlar:

- ✅ Selenium ile web otomasyonu  
- ✅ Proxy & IP rotasyonu ile network-aware bot çalıştırma  
- ✅ Web scraping + veri temizleme  
- ✅ SQLite / PostgreSQL entegrasyonu  
- ✅ Bot test & performans izleme  
- ✅ Anti-bot sistemlerini etik şekilde analiz eden simülasyon ortamı  
- ✅ Ölçeklenebilir RPA worker mimarisi  

---

## 🏗️ Proje Senaryosu (Gerçekçi Use Case)

### **Çoklu Web Platformundan Veri Toplayan Akıllı RPA Sistemi**

Sistem aşağıdaki adımları gerçekleştirir:

### 1️⃣ Çoklu Web Sitesine Login Olur
- Selenium automation  
- Session yönetimi  
- Cookie cache  

### 2️⃣ Sayfalardan Veri Toplar (Scraping)
- Ürün  
- Fiyat  
- İlan  
- İçerik  

### 3️⃣ Proxy & IP Rotation Katmanı Kullanır
- Her worker farklı IP  
- Rate limit simülasyonu  
- Request load balancing  

### 4️⃣ Veriyi Temizler & Normalize Eder
- Duplicate removal  
- Price normalization  
- Text cleaning  

### 5️⃣ SQLite / PostgreSQL’e Kaydeder  

### 6️⃣ Bot Sağlık Kontrolü Yapar
- Hız  
- Başarı oranı  
- Fail rate  

### 7️⃣ Dashboard Üzerinden İzlenir
- İşlenen site sayısı  
- Hata oranı  
- Ortalama işlem süresi  

---

## 🧩 Teknoloji–Modül Eşleşme Haritası

| Teknoloji / Özellik      | Projedeki Karşılığı                  |
| ------------------------ | ------------------------------------- |
| Selenium                 | Automation engine                     |
| Proxy & IP Rotation      | Proxy manager modülü                  |
| Bot korumaları           | Anti-bot detection simulator          |
| Web scraping             | Data extractor                        |
| Veri temizleme           | Cleaning pipeline                     |
| Database                 | SQLite / PostgreSQL                   |
| Bot test                 | QA + Monitoring                       |

---

## 🏛️ Sistem Mimarisi (Senior-Level)

RPA Orchestrator
↓
Task Scheduler
↓
Worker Pool (Selenium Bots)
↓
Proxy Manager
↓
Scraping Engine
↓
Data Cleaning Pipeline
↓
Database Layer
↓
Monitoring Dashboard


---

## 🛠️ Tech Stack

### Backend
- Python  
- Selenium  
- BeautifulSoup / Playwright  

### Proxy & Network
- Proxy rotation layer  
- Request throttling  

### Database
- SQLite (local)  
- PostgreSQL (production simulation)  

### DevOps
- Docker  
- Logging  
- Retry workers  

---

## 🤖 Core Modüller

### 1️⃣ Selenium Automation Engine
- Form doldurma  
- Button click  
- Navigation  
- Error handling  

### 2️⃣ Proxy & IP Manager
- IP pool  
- Rotation logic  
- Failure detection  

### 3️⃣ Scraping Engine
- HTML parsing  
- DOM extraction  
- Pagination handling  

### 4️⃣ Data Cleaning Pipeline
- Regex cleaning  
- Price parsing  
- Schema normalization  

### 5️⃣ Database Integration
- ORM layer  
- Insert / update / deduplication  

### 6️⃣ Bot Test & Health Monitor
- Success rate  
- Timeout tracking  
- Retry logic  

### 7️⃣ Dashboard
Gösterir:
- Toplanan veri sayısı  
- Bot başarı oranı  
- Ortalama response time  
- Fail logs  

---

## 🧪 Test Senaryoları

| Test Türü            | Amaç                          |
| -------------------- | ----------------------------- |
| Load test            | 50 bot paralel                |
| Proxy fail test      | IP düştüğünde davranış        |
| Scraping accuracy    | Veri doğruluğu                |
| Retry stress         | Rate limit simülasyonu        |

---

## 💼 CV’ye Girecek Proje Tanımı

### **Enterprise RPA Automation Platform**

> Developed a scalable RPA system using Selenium to automate multi-site web workflows, integrating proxy rotation, scraping pipelines, automated data cleaning, and relational database storage.  
> Implemented bot health monitoring, retry mechanisms, and performance analytics to optimize automation reliability and throughput.

---

# 📘 FULL PRD + TEKNİK DOKÜMANTASYON

## 🎯 Ürün Adı
**RPAFlow — Intelligent Web Automation & Data Pipeline**

---

## 🧾 Ürün Tanımı

RPAFlow; Selenium tabanlı botlar kullanarak web platformlarında otomatik gezinme, veri toplama (scraping), veri temizleme, proxy/IP rotasyonu, hata toleransı ve veritabanı entegrasyonu sağlayan profesyonel bir **RPA sistemidir**.

---

## 🎯 Hedefler

| Hedef                    | Açıklama              |
| ------------------------ | --------------------- |
| Ölçeklenebilir otomasyon | Çoklu bot desteği     |
| Stabil çalışma           | Retry & failover      |
| Veri doğruluğu           | Cleaning pipeline     |
| Performans ölçümü        | Bot health monitoring |
| Güvenli tasarım          | Etik ve yasal uyum    |

---

## ⚙️ Functional Requirements

| Özellik             | Açıklama                     |
| ------------------- | ---------------------------- |
| Selenium Automation | Web işlemleri otomasyonu     |
| Proxy Manager       | IP rotation & fail detection |
| Scraping Engine     | DOM parsing & pagination     |
| Data Cleaning       | Regex & normalization        |
| Database Layer      | SQLite / PostgreSQL          |
| Retry System        | Timeout & error recovery     |
| Logging             | İşlem kayıtları              |
| Performance Monitor | Bot başarı oranı             |

---

## 🔒 Non-Functional Requirements

| Alan              | Gereksinim                |
| ----------------- | ------------------------- |
| Performans        | Async worker desteği      |
| Güvenlik          | Secret vault, encryption  |
| Ölçeklenebilirlik | Worker pool               |
| Güvenilirlik      | %99 task completion hedef |
| Maintainability   | Modüler mimari            |

---

## 📊 KPI & Başarı Metrikleri

| KPI                    | Hedef |
| ---------------------- | ----- |
| Bot success rate       | %85+  |
| Avg task duration      | < 5s  |
| Retry recovery success | %70+  |
| Data accuracy          | %95+  |

---

## 🔁 Retry State Machine

INIT → RUNNING → SUCCESS
↘ FAIL → RETRY → FALLBACK


---

## 🛡️ Güvenlik & Etik

| Alan        | Önlem                   |
| ----------- | ----------------------- |
| Secrets     | .env vault              |
| PII         | Masking                 |
| Proxy usage | Yasal & etik throttling |
| Automation  | Platform TOS uyumlu     |

---

## 🚀 CV & Mülakat İçin Güçlü Konumlandırma

**Proje Başlığı:**  
**Enterprise RPA Automation Platform**

**Mülakatta söylenebilecek güçlü cümle:**

> *“This project demonstrates my ability to design scalable automation systems, handle real-world failure cases, manage scraping pipelines responsibly, and build maintainable RPA architectures.”*

---
