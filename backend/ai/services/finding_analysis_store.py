"""Small durable store for Finding AI analyses.

The path is configurable so tests and deployments can isolate state. Writes are
atomic and guarded within the process; corrupt state is never silently replaced.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import threading
from typing import Dict, Optional

from backend.database.models import FindingAIAnalysisModel


class FindingAnalysisStore:
    def __init__(self, path: Optional[str] = None) -> None:
        configured = path or os.getenv("DATATRUST_AI_ANALYSIS_STORE_PATH")
        self.path = Path(configured) if configured else Path("runtime/finding_ai_analyses.json")
        self._lock = threading.RLock()

    def _read(self) -> Dict[str, dict]:
        if not self.path.exists():
            return {}
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Finding analysis store must contain a JSON object")
        return payload

    def get(self, finding_id: str) -> Optional[FindingAIAnalysisModel]:
        with self._lock:
            item = self._read().get(finding_id)
            return FindingAIAnalysisModel.model_validate(item) if item else None

    def save(self, analysis: FindingAIAnalysisModel) -> FindingAIAnalysisModel:
        with self._lock:
            values = self._read()
            values[analysis.finding_id] = analysis.model_dump(mode="json")
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(self.path.suffix + ".tmp")
            temporary.write_text(json.dumps(values, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(temporary, self.path)
            return analysis
