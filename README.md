# Goal-Based Investment Platform

A full-stack goal-based investment platform for planning financial
goals, evaluating feasibility, analyzing mutual funds, understanding
tax-optimization opportunities, and generating data-driven fund
recommendations.

## Overview

The platform is designed around a goal-first investment workflow:

``` text
Goal Details
    ↓
Feasibility Analysis
    ↓
Strategy Preview
    ↓
Tax Optimization Insights
    ↓
Fund Evaluation
    ↓
Deterministic Recommendation Ranking
    ↓
User Review & Confirmation
```

The system separates deterministic financial calculations from
explanatory/intelligent layers so that recommendations remain traceable
and verifiable.

## Core Features

### Goal Planning

Users can create goals such as:

-   Vacation
-   House
-   Car
-   Education
-   Wedding
-   Retirement
-   Healthcare
-   Custom goals

Goal inputs include target amount, target date, SIP/lumpsum
contributions, risk level, inflation assumptions, priority, deadline
flexibility, and importance.

### Goal Feasibility

The feasibility engine evaluates whether the planned investment can
reach the target.

Possible outcomes include:

-   `ACHIEVABLE`
-   `STRETCHED`
-   `DIFFICULT`
-   `UNREALISTIC`

Alternative strategies can be generated, such as increasing
contributions or extending the timeline.

### Mutual Fund Analytics

The platform evaluates funds using:

  -----------------------------------------------------------------------
  Metric                              Purpose
  ----------------------------------- -----------------------------------
  CAGR                                Annualized historical return

  Volatility                          Historical return variation

  Maximum Drawdown                    Peak-to-trough decline

  Sharpe Ratio                        Return relative to total risk

  Sortino Ratio                       Return relative to downside risk

  Alpha                               Benchmark-relative excess
                                      performance

  Beta                                Sensitivity to benchmark movements

  R²                                  Benchmark explanatory power

  Rolling 7-Year Consistency          Long-term consistency relative to
                                      the benchmark
  -----------------------------------------------------------------------

### Data Confidence

Each fund has a separate data-confidence classification:

-   `HIGH`
-   `MEDIUM`
-   `LOW`
-   `INSUFFICIENT`

Confidence considers historical observations, data freshness, available
history, and peer reliability.

Funds with insufficient data are not assigned a recommendation score.

### Deterministic Recommendation Engine

Funds are ranked against peers in the same subcategory instead of being
returned alphabetically.

The recommendation score is normalized to `0–100`.

Higher CAGR, Sharpe, and Sortino generally improve the score, while
lower volatility and smaller drawdowns improve the score.

Missing metrics are handled through weight re-normalization, subject to
the engine's eligibility rules.

The score is persisted separately as:

``` text
asset_metrics.recommendation_score
```

### Benchmark Integration

Benchmark infrastructure supports benchmark-relative analytics through:

-   Benchmark mappings
-   Historical benchmark observations
-   NIFTY data ingestion
-   Benchmark repository
-   Benchmark ingestion service

This supports Alpha, Beta, R², and rolling consistency calculations.

### Tax Optimization

Tax information is presented separately from fund ranking.

The tax layer can provide educational insights around:

-   Section 80C
-   ELSS
-   Equity mutual-fund taxation
-   Debt mutual-fund taxation
-   ELSS lock-in considerations
-   Potential tax-saving capacity

Tax advantages do not directly override fund-quality ranking. Tax
information is educational and should be independently verified where
professional advice is required.

## Architecture

``` text
Frontend
   │
   ▼
FastAPI API
   │
   ├── Goals
   ├── Feasibility
   ├── Recommendations
   ├── Funds
   ├── Universe
   ├── Portfolio
   ├── Simulation
   ├── Retirement
   ├── Emergency Fund
   ├── Dashboard
   ├── Chatbot
   └── Tax / Strategy
        │
        ▼
   Service Layer
        │
        ├── Goal Strategy
        ├── Feasibility Engine
        ├── Analytics Engine
        ├── Metrics Engine
        ├── Recommendation Engine
        └── Tax Opportunity Engine
        │
        ▼
   Repository Layer
        │
        ▼
      Supabase
        │
        ├── Goals
        ├── Fund Universe
        ├── Asset Metrics
        └── Benchmark Data
```

## Project Structure

``` text
.
├── backend/
│   └── app/
│       ├── core/
│       ├── db/
│       │   └── migrations/
│       ├── middleware/
│       └── modules/
│           ├── auth/
│           ├── chatbot/
│           ├── dashboard/
│           ├── emergency_fund/
│           ├── feasibility_engine/
│           ├── funds/
│           ├── goals/
│           ├── learning/
│           ├── portfolio/
│           ├── profile/
│           ├── recommendation/
│           ├── retirement/
│           ├── simulation/
│           └── universe/
│               ├── providers/
│               └── recommendation/
│
└── frontend/
    └── src/
        ├── components/
        ├── pages/
        ├── services/
        └── types/
```

## Important API Endpoints

### Goals

``` http
POST /api/v1/goals
GET  /api/v1/goals
GET  /api/v1/goals/{goal_id}
PUT  /api/v1/goals/priority
```

### Strategy

``` http
POST /api/v1/goals/strategy/preview
POST /api/v1/goals/strategy/finalize
POST /api/v1/goals/strategy/recommendations
```

### Feasibility

``` http
POST /api/v1/goals/feasibility/preview
POST /api/v1/goals/feasibility/apply
```

### Universe / Recommendation Computation

``` http
GET  /api/v1/universe/recommendations
POST /api/v1/universe/recommendations/compute
```

## Database

The application uses Supabase/PostgreSQL.

Important data areas include:

``` text
goals
asset_universe
asset_metrics
fund_cache
benchmark_mapping
benchmark_historical_observations
```

Recommendation scores are stored in `asset_metrics.recommendation_score`
and indexed for efficient ranking.

## Local Development

### Backend

``` bash
cd backend
python -m venv venv
```

Windows:

``` bash
venv\Scripts\activate
```

Install dependencies:

``` bash
pip install -r requirements.txt
```

Run the API:

``` bash
uvicorn app.main:app --reload
```

Health check:

``` text
GET /health
```

Expected response:

``` json
{
  "status": "ok"
}
```

### Environment

Use the project's environment configuration / `.env.example`.

Typical backend variables include:

``` env
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=
SENTRY_DSN=
ENV=
ALLOWED_ORIGINS=
```

Never commit real secrets.

## Testing

Run the backend test suite:

``` bash
venv\Scripts\pytest
```

The test suite covers goal planning, feasibility, recommendation
scoring, confidence handling, benchmark providers, fund operations,
universe refresh, and strategy/tax logic.

## Data Pipeline

``` text
External Fund Providers
        ↓
Provider Layer
        ↓
Universe Ingestion
        ↓
asset_universe
        ↓
Historical NAV Data
        ↓
Analytics Engine
        ↓
asset_metrics
        ↓
Benchmark Comparison
        ↓
Recommendation Scoring
        ↓
recommendation_score
        ↓
Ranked Fund Recommendations
```

## Design Principles

### Deterministic

The same inputs and data should produce reproducible recommendation
results.

### Data-Driven

Fund selection should be based on evaluation metrics rather than
alphabetical ordering or arbitrary selection.

### Confidence-Aware

The platform distinguishes the quality of the data from the quality of
the fund.

### Separation of Concerns

Metrics, confidence, recommendation scores, feasibility, tax insights,
and user preferences remain separate concepts.

### Interactive

Users should be able to review feasibility, alternatives, strategy, tax
considerations, and recommendations before confirming a goal.

### Safety Over False Precision

The system should avoid producing misleading recommendations when
sufficient data is unavailable.

## Security

The backend uses authentication, user-scoped Supabase clients, Row Level
Security, environment-based secrets, and sanitized error handling.

Never commit:

-   JWT tokens
-   Supabase keys
-   Passwords
-   Other credentials

## Disclaimer

This project is an investment-planning and educational decision-support
application. Historical performance does not guarantee future returns.
Tax rules and market conditions can change. Tax-related information
should be independently verified, and users should consult qualified
financial or tax professionals where appropriate.

## Development Status

The platform is actively evolving toward a complete interactive
goal-based investment decision-support system.

Current major layers include:

1.  Fund data ingestion
2.  Fund analytics
3.  Benchmark evaluation
4.  Data confidence
5.  Recommendation scoring
6.  Goal feasibility
7.  Strategy planning
8.  Tax optimization insights
9.  Interactive recommendations
10. User confirmation
