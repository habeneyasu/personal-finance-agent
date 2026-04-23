# PFIP Dashboard — Frontend

Minimal, beautiful React dashboard for the Personal Finance Intelligence Platform MVP.

## Tech Stack

- **Vite** + **React** + **TypeScript**
- **Tailwind CSS** (via CDN)
- **Recharts** for charts
- **Axios** for API calls

## Setup

```bash
cd frontend
npm install
```

## Running Locally

**1. Start the backend API server:**

```bash
# From project root
uvicorn scripts.run_api_local:app --port 8000 --reload
```

**2. Start the frontend dev server:**

```bash
# From frontend/
npm run dev
```

The dashboard will be available at **http://localhost:3000**

## Features

### Overview Tab (Default)
- 3 stat cards: Total Income, Total Expenses, Net Savings
- Bar chart: monthly income vs expenses (last 3 months)
- Pie chart: expenses by category
- Auto-refreshes every 3 seconds

### Transactions Tab
- Two columns: Income (left) and Expenses (right)
- Add forms for each type
- Recent entries list (last 10)
- AI-assigned categories for expenses

### Goals Tab
- Goal cards with progress bars
- Current/target amounts
- Predicted completion dates
- Add new goals

### Insights Tab
- Chat-style interface
- Ask natural language questions about your finances
- AI-powered answers based on your data

## Design

- **Dark theme**: Deep navy/slate background (#0f172a, #1e293b)
- **Accent colors**: Emerald green (#10b981) for positive, Rose (#f43f5e) for negative
- **Font**: Inter (via Google Fonts)
- **Smooth transitions** on data updates
- **Professional, minimal** — looks like a fintech product

## API

All API calls go to `http://localhost:8000` (hardcoded for local demo).

No authentication required for local development — the backend bypasses Cognito when `ENVIRONMENT=local`.

## Build for Production

```bash
npm run build
```

Output will be in `dist/` directory.
