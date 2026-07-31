# Graph Report - .  (2026-07-29)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 121 nodes · 161 edges · 24 communities (21 shown, 3 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 3 edges (avg confidence: 0.7)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `382fc6d5`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- log_antigravity.py
- graph.py
- datetime
- main.py
- example_tool.py
- routes.py
- submit_log.py
- conftest.py
- test_routes.py
- test_graph.py
- _pyrun.sh
- setup.sh
- setup_hooks.sh script

## God Nodes (most connected - your core abstractions)
1. `main()` - 9 edges
2. `iter_user_inputs()` - 8 edges
3. `AgentState` - 8 edges
4. `_conv_cwds()` - 6 edges
5. `get_settings()` - 6 edges
6. `build_graph()` - 5 edges
7. `analyze_node()` - 5 edges
8. `respond_node()` - 5 edges
9. `chat()` - 5 edges
10. `get_brain_dirs()` - 4 edges

## Surprising Connections (you probably didn't know these)
- `build_graph()` --indirect_call--> `analyze_node()`  [INFERRED]
  src/agents/graph.py → src/agents/nodes/example_node.py
- `build_graph()` --indirect_call--> `respond_node()`  [INFERRED]
  src/agents/graph.py → src/agents/nodes/example_node.py
- `should_continue()` --references--> `AgentState`  [EXTRACTED]
  src/agents/graph.py → src/agents/state.py
- `analyze_node()` --references--> `AgentState`  [EXTRACTED]
  src/agents/nodes/example_node.py → src/agents/state.py
- `respond_node()` --references--> `AgentState`  [EXTRACTED]
  src/agents/nodes/example_node.py → src/agents/state.py

## Import Cycles
- None detected.

## Communities (24 total, 3 thin omitted)

### Community 0 - "log_antigravity.py"
Cohesion: 0.18
Nodes (20): build_entry(), _conv_cwds(), _conv_matches_repo(), extract_user_prompt(), get_brain_dirs(), get_logged_entry_ids(), git(), iter_user_inputs() (+12 more)

### Community 1 - "graph.py"
Cohesion: 0.22
Nodes (13): build_graph(), Route based on whether an error occurred during analysis., should_continue(), analyze_node(), Tạo response từ analysis., # TODO: Thêm logic tạo response thực tế, Phân tích query từ user., # TODO: Thêm logic phân tích thực tế (+5 more)

### Community 2 - "datetime"
Cohesion: 0.22
Nodes (11): datetime, detect_tool(), git(), main(), normalize(), Detect which AI tool sent this hook event. Priority: 1. --tool=NAME CLI…, Normalize tool-specific payload to common log entry., git() (+3 more)

### Community 3 - "main.py"
Cohesion: 0.26
Nodes (9): BaseSettings, ChatOpenAI, FastAPI, get_settings(), Settings, health(), lifespan(), get (+1 more)

### Community 4 - "example_tool.py"
Cohesion: 0.27
Nodes (9): AST, calculate(), _eval_node(), Tìm kiếm thông tin trong knowledge base. Args: query: Câu hỏi cần tìm kiếm…, # TODO: Implement actual search logic (e.g., RAG with vector store), Tính toán biểu thức toán học an toàn (không dùng eval). Hỗ trợ: +, -, *, /, //,…, Recursively evaluate AST node using safe operators only., search_knowledge() (+1 more)

### Community 5 - "routes.py"
Cohesion: 0.33
Nodes (8): BaseModel, post, agent_status(), chat(), get, Kiểm tra trạng thái agent., ChatRequest, ChatResponse

### Community 6 - "submit_log.py"
Cohesion: 0.43
Nodes (6): _archive(), main(), Path, Append pending file to today's archive. Never overwrites existing data., Failure path: put pending back at LOG_FILE so the next push retries. If hook…, _restore_pending()

### Community 7 - "conftest.py"
Cohesion: 0.40
Nodes (5): fixture, client(), mock_llm(), Async HTTP client for testing API endpoints., Mock LLM to avoid calling OpenAI during tests. Usage in test: def…

### Community 8 - "test_routes.py"
Cohesion: 0.60
Nodes (4): asyncio, test_agent_status(), test_chat_empty_message(), test_health()

### Community 9 - "test_graph.py"
Cohesion: 0.67
Nodes (3): asyncio, test_agent_basic_flow(), test_agent_state_structure()

## Knowledge Gaps
- **3 isolated node(s):** `_pyrun.sh script`, `setup.sh script`, `setup_hooks.sh script`
  These have ≤1 connection - possible missing edges or undocumented components.
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `iter_user_inputs()` connect `log_antigravity.py` to `datetime`?**
  _High betweenness centrality (0.020) - this node is a cross-community bridge._
- **What connects `_pyrun.sh script`, `setup.sh script`, `setup_hooks.sh script` to the rest of the system?**
  _3 weakly-connected nodes found - possible documentation gaps or missing edges._