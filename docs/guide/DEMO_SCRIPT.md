# DataTrust OS v5 Operational Trust Console.0 — Demo Script (15 min)

## Setup (2 min)

```bash
# Start backend
cd P-086 && uv run uvicorn src.main:app --reload --port 8000

# Start frontend
cd frontend-v3 && pnpm dev
```

Open browser: `http://localhost:5174`

## Demo Flow

### 1. Dashboard Overview (2 min)
- Show KPI cards: total records, quality score, quarantined count
- Show activity timeline
- Explain 5 data sources: Google Maps, Play Store, Shopee, UIT-VSFC, Xanh SM

### 2. Data Sources (2 min)
- Navigate to Sources page
- Show raw snapshots with SHA-256 hashes
- Click "Run Pipeline" to trigger analysis

### 3. Agent Traces (3 min)
- Navigate to Traces page
- Show ReAct loop: Thought → Action → Observation
- Highlight cross-domain diagnosis (NLP + telemetry)
- Show token cost per step

### 4. HITL Queue (3 min)
- Navigate to HITL page
- Show pending rule proposals from agent
- **Approve** one rule (show impact preview)
- **Edit** another rule (modify expression)
- **Reject** a low-confidence rule
- Show audit trail updates in real-time

### 5. Quarantine Explorer (1 min)
- Navigate to Quarantine page
- Show quarantined records with lineage hash
- Show originating rule

### 6. Evaluation Results (2 min)
- Show C0 vs C1 vs A1 comparison table
- Highlight: A1 detects 9/9 fault families vs C0's 2/9
- Show agentic necessity justification

## Key Talking Points

1. **Why Agent?** Cross-domain root-cause diagnosis impossible with rules alone
2. **Vietnamese NLP**: 353 teen-code entries, aspect extraction
3. **Safety**: HITL gate prevents autonomous execution
4. **Measurable**: Precision ≥80%, Recall ≥C1+10pp
5. **Architecture**: ReAct bounded loop, 6 tools, 5 agents
