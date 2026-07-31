# Mentor Questions

## Objective
Structured questions for the mentor sessions (Wed/Sat).

## Batch 1: Scope & Direction (Sat 2 Aug or Wed 5 Aug)
1. **Pain-point validation depth:** How many interviews/walkthroughs do you expect before the first demo? Is synthetic-only evaluation acceptable for the MVP, or must we show at least one real user?
2. **Dataset choice:** We plan to use NYC FHVHV trip data (public, ride-hailing, 20M+ rows). Is this acceptable as a proxy for "Dịch vụ gọi xe X" or should we find Vietnamese data?
3. **Scope boundary:** DATA-02 includes scheduled monitoring + anomaly ML. We've scoped down to one-shot onboarding + optional anomaly. Is this too narrow or is the wedge correct?
4. **Agentic claim:** The gate (A1 must beat C1 by >=10pp recall or >=25% time reduction) is from our internal design. Do you agree with these thresholds?
5. **Demo audience:** Who will see the final demo? Technical mentors only, or also business stakeholders?

## Batch 2: Technical (Wed 5 Aug)
6. **LLM provider:** We plan provider-agnostic adapter (Gemini/GPT-4o/Claude). Any preference for the demo?
7. **Database:** DuckDB for MVP (no infra overhead) vs. PostgreSQL (closer to production reality)?
8. **UI depth:** Guided workflow in React vs. Streamlit prototype? How polished must the UI be for the demo?

## Batch 3: Evaluation (Sat 8 Aug)
9. **Error injection:** We plan 5%/10%/20% error rates at easy/medium/hard difficulty. Is this sufficient?
10. **Ground truth:** Should we hand-label a subset of the FHVHV data or is synthetic injection enough?
11. **Anomaly scope:** Is the anomaly ML stretch goal worth Sprint 4 time, or should we invest in polishing HITL instead?
12. **Business validation depth:** Is a competitor landscape + 3 user interviews sufficient, or do you expect a full business plan with pricing model?
