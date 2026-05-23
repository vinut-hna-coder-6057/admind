# ▶️ AdMind — Smart Ad Recommendation Engine

AdMind is an AI-powered ad recommendation system built for YouTube-style platforms. It intelligently matches ads to video content using semantic embeddings, user personalization, CTR optimization, and feedback learning — all wrapped in a sleek Streamlit dashboard with a FastAPI backend.

---

## ✨ Features

- **Semantic Ad Matching** — Uses `sentence-transformers` to embed video titles and match them with the most relevant ads by description and category
- **User Personalization** — Tailors recommendations based on user type: `student`, `developer`, `gamer`, `professional`, or `casual`
- **Mode Awareness** — Respects viewing modes (`study` / `casual`) and detects content-mode conflicts with a smart popup alert
- **CTR Optimization** — Boosts ads with historically higher click-through rates
- **Feedback Learning** — Adjusts scores based on user thumbs-up/thumbs-down feedback
- **Diversity Control** — Penalizes recently shown ad categories to avoid repetition
- **Analytics Dashboard** — Visualizes ad impressions, CTR trends, feedback stats, and recommendation history
- **Admin Panel** — Password-protected panel for managing ads and viewing system metrics
- **Rate Limiting** — API is protected with `slowapi` (10 requests/minute per IP)

---

## 🏗️ Project Structure

```
admind/
├── backend/
│   ├── api.py                  # FastAPI app & routes
│   ├── config/
│   │   └── config.py           # Env vars & ranking weights
│   ├── database/
│   │   ├── connection.py       # SQLite connection & init
│   │   ├── ads.py              # Ad CRUD
│   │   ├── feedback.py         # Feedback store & scores
│   │   ├── history.py          # Recommendation history
│   │   └── analytics.py        # CTR & impression tracking
│   ├── services/
│   │   ├── recommender_engine.py   # Core ranking logic
│   │   ├── embedding_service.py    # Sentence-transformer wrapper
│   │   ├── video_understanding.py  # Video category detection
│   │   ├── vector_store.py         # FAISS vector index
│   │   ├── dataset_service.py      # CSV dataset loader
│   │   ├── youtube_api.py          # YouTube Data API client
│   │   ├── analytics_service.py    # Analytics helpers
│   │   └── category_map.py         # Category ID → name mapping
│   ├── datasets/
│   │   ├── ads_dataset.csv
│   │   ├── videos_dataset.csv
│   │   └── youtube_analytics.csv
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── app.py                  # Streamlit entry point
│   ├── requirements.txt
│   └── ui/
│       ├── dashboard_page.py
│       ├── analytics_page.py
│       ├── admin_page.py
│       ├── charts.py
│       ├── components.py
│       └── styles.py
└── README.md
```

---

## ⚙️ Setup

### 1. Clone the repository

```bash
git clone https://github.com/your-username/admind.git
cd admind
```

### 2. Create a virtual environment

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
```

### 3. Configure environment variables

```bash
cp backend/.env.example backend/.env
```

Edit `backend/.env`:

```env
YOUTUBE_API_KEY=your_youtube_api_key
ADMIN_PASSWORD=your_secure_password
DB_NAME=admind.db
```

### 4. Install dependencies

**Backend:**
```bash
pip install -r backend/requirements.txt
```

**Frontend:**
```bash
pip install -r frontend/requirements.txt
```

---

## 🚀 Running the App

### Start the Backend API

```bash
uvicorn backend.api:app --reload
```

The API will be available at `http://localhost:8000`.

### Start the Frontend

```bash
cd frontend
streamlit run app.py
```

The dashboard will open at `http://localhost:8501`.

---

## 📡 API Reference

### `GET /`
Health check — returns a running status message.

### `GET /health`
Returns `{ "status": "healthy" }`.

### `POST /recommend-ad`

Rate limited to **10 requests/minute** per IP.

**Request body:**
```json
{
  "title": "How to build a neural network in Python",
  "mode": "study",
  "user_type": "student"
}
```

**`user_type` options:** `casual` | `student` | `developer` | `gamer` | `professional`  
**`mode` options:** `study` | `casual`

**Response:**
```json
{
  "ad_name": "Coursera Pro",
  "video_type": "education",
  "confidence": 87,
  "mode_conflict": false,
  "mode_message": "",
  "adaptive_popup": false
}
```

---

## 🧠 How the Ranking Works

Each candidate ad is scored using a weighted formula:

| Signal | Weight |
|---|---|
| Semantic similarity (title ↔ ad description/category) | ×10 |
| Personalization match (user type ↔ ad category) | +4 |
| Mode match | +2 |
| CTR score | ×3 |
| Feedback score | ×1.5 |
| Diversity penalty (recently shown category) | −4 |

Video category is detected via majority voting over the top-5 FAISS nearest neighbours from the video dataset.

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Backend API | FastAPI + Uvicorn |
| Frontend | Streamlit |
| Embeddings | `sentence-transformers` (`all-MiniLM-L6-v2`) |
| Vector Search | FAISS (`faiss-cpu`) |
| Database | SQLite |
| Charts | Plotly |
| Rate Limiting | SlowAPI |

---

## 🔐 Admin Panel

Access the admin panel by logging in with your `ADMIN_PASSWORD` from the sidebar. The panel lets you view recommendation history, manage ads, and inspect system analytics.

---

## 📄 License

MIT License. See [LICENSE](LICENSE) for details.
