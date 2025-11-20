# Ruh

pronounced [ˈɹu] - rooh

> AI-powered product safety analysis for conscious consumers - detect harmful substances and make informed choices.

**Ruh** is a Chrome extension that analyzes Amazon products for harmful substances (allergens, PFAS, and other chemicals) using Claude AI to help you make safer purchasing decisions.

## What It Does

1. **Detects Products**: Automatically recognizes when you're viewing an Amazon product
2. **Analyzes Safety**: Claude AI agent examines ingredients for allergens, PFAS, and other harmful substances
3. **Scores Harm Level**: Clear visual indicator (0-100) showing how safe/risky the product is
4. **Detailed Breakdown**: Lists specific allergens, PFAS compounds, and other concerns detected
5. **Fast & Cached**: Results are cached for 30 days for instant subsequent views

## Quick Start - Try the Extension

### Prerequisites
- Node.js 18+ and npm installed
- Google Chrome browser

### Build & Install

1. **Clone the repository**
   ```bash
   git clone https://github.com/RSHVR/ruh.git
   cd ruh/extension
   ```

2. **Install dependencies**
   ```bash
   npm install
   ```

3. **Set up environment variables**
   ```bash
   cp .env.example .env
   ```

   The `.env` file is already configured with the backend API. No changes needed - it includes:
   - Backend URL: `https://ruh-api-948739110049.us-central1.run.app`
   - API Key: Pre-configured for demo access

4. **Build the extension**
   ```bash
   npm run build
   ```
   This creates a `dist` folder with the compiled extension.

5. **Load into Chrome**
   - Open Chrome and navigate to `chrome://extensions/`
   - Enable "Developer mode" (toggle in top-right)
   - Click "Load unpacked"
   - Select the `extension/dist` folder
   - The Ruh extension is now installed!

6. **Try it out**
   - Visit any Amazon product page (e.g., https://amazon.com/dp/B004D24D0S)
   - The extension will automatically analyze the product
   - Click the floating button to view the safety analysis

## Architecture

- **Chrome Extension**: Svelte 5 + TypeScript with content scripts and sidebar UI
- **Backend API**: FastAPI (Python) server using Claude Agent SDK with web scraping
- **AI Analysis**: Claude Sonnet 4.5 performs ingredient analysis with web search capabilities
- **Database**: Supabase (PostgreSQL) for caching analysis results
- **Deployment**: Google Cloud Run with automatic CI/CD from GitHub

## Documentation

- **[CLAUDE.md](./CLAUDE.md)**: Complete system documentation with function-level flows
- **[ruh-brand-guide.md](./ruh-brand-guide.md)**: Brand identity and design guidelines
- **Backend**: FastAPI server with clean architecture ([backend/README.md](./backend/README.md))
- **Extension**: Svelte 5 Chrome extension ([extension/README.md](./extension/README.md))
- **Future Plans**: Planned features and improvements ([backend/supabase/FUTURE_IMPROVEMENTS.md](./backend/supabase/FUTURE_IMPROVEMENTS.md))

## Authors

Arshveer Gahir

## License

All Rights Reserved
