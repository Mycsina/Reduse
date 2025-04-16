# Reduse

A modern webapp for listing analysis.

What it does:
- Parses listings from used listing websites
- Analyzes what products are there described
- Generates pricing data across different dimensions (currently models, planned across the different item types, brands, etc)
- Provides an interface to analyze pricing data 

## 🏗️ Architecture

### Backend (Python)

- FastAPI for the REST API
- MongoDB Atlas with Beanie ODM for data storage
- Crawlee w/ Playwright, BeautifulSoup4 for web scraping
- Multiple AI providers (Google AI, Groq) for analysis
- Task scheduling with APScheduler
- Poetry for dependency management

### Frontend (TypeScript)

- Next.js 13+ with App Router
- Tailwind CSS for styling
- React Query for data fetching
- Radix UI for accessible components

## 🚀 Getting Started

### Prerequisites

- Python 3.13+
- JS Runtime (Node/Bun/etc, tested w/ Bun)
- Docker and Docker Compose
- MongoDB Atlas cluster with network access configured
- API keys for:
  - Google AI
  - Groq

### Environment Setup

1. Clone the repository:

```bash
git clone https://github.com/yourusername/vroom.git
cd vroom
```

2. Set up environment variables:

Backend (.env):

```env
API_KEY=your_api_key
ATLAS_USER=your_mongodb_user
ATLAS_PASSWORD=your_mongodb_password
GOOGLE_API_KEY=your_google_ai_key
GROQ_API_KEY=your_groq_key
MONGODB_URI=mongodb+srv://<user>:<password>@vroom.k7x4g.mongodb.net/
```

Frontend (.env):

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### Running with Docker

1. Build and start the containers:

```bash
docker-compose up --build
```

2. Access the application:

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/docs

### Development Setup

Backend:

```bash
cd backend
poetry install
fastapi dev start.py
```

Frontend:

```bash
cd frontend
bun i
bun run dev
```

## 📚 Documentation

- Backend API documentation: http://localhost:8000/docs
- Frontend component documentation: http://localhost:3000/docs (coming soon)
