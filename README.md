# Exchange Platform Backend

This is a modular backend project designed for handling core functionalities of a cryptocurrency exchange platform, written in Python using Django. The architecture is organized into several apps, each responsible for a distinct domain of the system.

---

## 🔧 Structure Overview

### `orders`
Handles:
- Core models: `Order`, `Trade`
- Order management and matching logic
- The `services.py` file contains the **Matching Engine**, a critical component that ensures safe and accurate order matching and trade execution.

### `orderbook`
Responsibilities:
- Display and update the **order book**
- Synchronize data between **Redis** and the primary **PostgreSQL** database
- Isolated into a separate app to allow future scalability and feature expansion

### `currencies`
Includes:
- `Currency` model: Manage available currencies (admin panel)
- `Market` model: Define tradable markets (e.g., BTC_USDT)

### `core`
Contains:
- Project settings and base configurations
- An `AbstractBaseModel` used by other models to ensure consistency and DRY principles

### `api`
Implements:
- All API endpoints with versioning (`apis/v1/`)
- Organized views, serializers, URLs, and tests based on domain logic

### `tasks`
Originally created to handle background tasks (Celery integration). This app is now deprecated and all related Celery settings and code have been commented out after initial evaluation.

---

## ✅ Supported Functionalities (as of latest update)

- Create new currencies
- Create new markets
- Retrieve list of active markets
- Submit `market` and `limit` orders
- Cancel orders
- Retrieve the order book

---

## ⚙️ Performance Optimizations

- **Redis** is used to serve the order book with high performance.
- **Redis collections** are located at the project root.
- Redis is updated from PostgreSQL after critical events to ensure consistency.

---

## 📦 Technologies Used

- Python
- Django & Django REST Framework
- PostgreSQL
- Redis
- Celery (commented out)
- Docker (optional for deployment)

---

## 📁 Project Structure (Simplified)



```text
├── core/
│   ├── models.py          # Abstract BaseModel used by all apps
│   ├── settings.py        # Global Django project settings
│
├── currencies/
│   ├── models.py          # Currency, Market models
│   ├── services.py        # Logic for managing currencies and markets
│   ├── admin.py           # Admin panel configuration for Currency and Market
│
├── orders/
│   ├── models.py          # Order, Trade models
│   ├── services.py        # MatchingEngine logic for order matching
│
├── orderbook/
│   ├── services.py        # Order book update & sync logic (Redis <-> DB)
│   ├── consumers.py       # WebSocket consumers for real-time updates
│
├── tasks/
│   ├── tasks.py           # Celery tasks for accounting and sync (Deprecated)
│   ├── tests.py
│
├── api/
│   └── apis/v1/
│       ├── views/         # DRF views organized by domain
│       ├── serializers/   # DRF serializers
│       ├── urls.py        # API routes (versioned)
│       ├── tests.py
│
├── manage.py
├── postman_collection.json
├── requirements.txt
