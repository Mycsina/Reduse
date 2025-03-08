# Vroom

A modern web application for intelligent product analysis and tracking, built with FastAPI and Next.js.

## 🌟 Features

- **AI-Powered Analysis**: Utilizes multiple AI providers (Google AI, Groq) for intelligent product analysis
- **Real-time Product Tracking**: Monitor and analyze product listings from various sources
- **Modern Web Interface**: Built with Next.js 13+ and Tailwind CSS
- **Scalable Backend**: FastAPI backend with MongoDB Atlas cloud database integration
- **Automated Scraping**: Configurable web scraping with Playwright
- **Task Scheduling**: Built-in job scheduler for automated tasks
- **eBay Integration**: Native integration with eBay's APIs

## 📋 Implemented Epics

### AI and Analysis

- ✅ Multi-provider AI integration (Google AI, Groq)
- ✅ Product listing analysis with structured output
- ✅ Intelligent text generation and processing
- ✅ Semantic embedding and similarity search

### Data Collection

- ✅ Automated web scraping with Playwright
- ✅ eBay API integration
- ✅ Scheduled data collection tasks
- ✅ Rate limiting and retry mechanisms

### Task Management

- ✅ Background task scheduling
- ✅ Task status monitoring
- ✅ Failure recovery and retry logic
- ✅ Task analytics and reporting

### Analytics

- ✅ Usage tracking and monitoring
- ✅ Performance analytics
- ✅ Query analysis and optimization
- ✅ Custom analytics dashboards

### User Management

- ✅ Subscription management
- ✅ Usage quotas and limits
- ✅ Payment processing
- ✅ User preferences

### Frontend Features

- ✅ Real-time listing updates
- ✅ Advanced search and filtering
- ✅ Comparison tools
- ✅ Task scheduling interface
- ✅ Analysis visualization

## 🏗️ Architecture

### Backend (Python)

- FastAPI for the REST API
- MongoDB Atlas (cloud) with Beanie ODM for data storage
- Multiple AI providers (Google AI, Groq) for analysis
- Task scheduling with APScheduler
- Playwright for web scraping
- Poetry for dependency management

### Frontend (TypeScript)

- Next.js 13+ with App Router
- Tailwind CSS for styling
- React Query for data fetching
- Radix UI for accessible components
- Server-side rendering (SSR)

## 🚀 Getting Started

### Prerequisites

- Python 3.13+
- Node.js 20+
- Docker and Docker Compose
- MongoDB Atlas cluster with network access configured
- API keys for:
  - Google AI
  - Groq
  - eBay (optional)

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
EBAY_APP_ID=your_ebay_app_id
EBAY_CERT_ID=your_ebay_cert_id
EBAY_APP_CREDENTIALS=your_ebay_credentials
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
poetry run python start.py
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

## 📚 Documentation

- Backend API documentation: http://localhost:8000/docs
- Frontend component documentation: http://localhost:3000/docs (coming soon)

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
