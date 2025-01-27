# Vroom - Vehicle Price Analysis Tool

A tool for analyzing vehicle prices across multiple marketplaces.

## Features

- Multi-source data collection (OLX, eBay)
- AI-powered listing analysis
- Price trend analysis
- Similar listing detection
- Automated data collection

## Setup

1. Clone the repository
2. Install dependencies with Poetry:
   ```bash
   poetry install
   ```
3. Set up environment variables in `.env`:

   ```env
   # API Settings
   API_KEY=your_api_key
   ENVIRONMENT=development

   # MongoDB Settings
   ATLAS_USER=your_mongodb_user
   ATLAS_PASSWORD=your_mongodb_password

   # AI Settings
   GEMINI_API_KEY=your_gemini_api_key
   GROQ_API_KEY=your_groq_api_key

   # eBay API Settings
   EBAY_APP_ID=your_ebay_app_id
   EBAY_CERT_ID=your_ebay_cert_id
   EBAY_APP_CREDENTIALS=your_base64_encoded_credentials
   ```

## eBay API Setup

1. Create an eBay developer account at https://developer.ebay.com
2. Create a new application in the developer portal
3. Get your App ID and Cert ID
4. Generate your application credentials:
   ```bash
   echo -n "your_app_id:your_cert_id" | base64
   ```
5. Add the credentials to your `.env` file

## Usage

1. Start the server:

   ```bash
   poetry run python -m start
   ```

2. Access the API at http://localhost:8000

## API Endpoints

- `GET /listings/`: Get all listings
- `GET /listings/analyze`: Analyze listings
- `GET /listings/status`: Get analysis status
- `POST /listings/scrape`: Scrape new listings

## Development

1. Install development dependencies:

   ```bash
   poetry install --with dev
   ```

2. Run tests:
   ```bash
   poetry run pytest
   ```

## License

MIT
