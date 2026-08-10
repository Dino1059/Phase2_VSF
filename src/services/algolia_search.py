import logging
from typing import Any, Dict, List, Optional
from algoliasearch.search.client import SearchClientSync
from algoliasearch.search.models import SearchParamsObject
from src.config import get_settings
from src.db.connection import get_db

logger = logging.getLogger(__name__)


class AlgoliaSearchService:
    def __init__(self):
        settings = get_settings()
        self.app_id = settings.algolia_app_id
        self.write_key = settings.algolia_write_key
        self.search_key = settings.algolia_search_key
        self.index_name = "datatrust_entities"

        self._write_client: Optional[SearchClientSync] = None
        self._search_client: Optional[SearchClientSync] = None

    @property
    def write_client(self) -> SearchClientSync:
        if self._write_client is None:
            if not self.app_id or not self.write_key:
                raise ValueError("Algolia credentials (ALGOLIA_APPLICATION_ID / ALGOLIA_API_WRITE_KEY) are missing.")
            self._write_client = SearchClientSync(self.app_id, self.write_key)
        return self._write_client

    @property
    def search_client(self) -> SearchClientSync:
        if self._search_client is None:
            key = self.search_key or self.write_key
            if not self.app_id or not key:
                raise ValueError("Algolia credentials (ALGOLIA_APPLICATION_ID / ALGOLIA_SEARCH_API_KEY) are missing.")
            self._search_client = SearchClientSync(self.app_id, key)
        return self._search_client

    def index_entities(self, objects: List[Dict[str, Any]], index_name: Optional[str] = None) -> List[Any]:
        if not objects:
            return []
        idx_name = index_name or self.index_name
        response = self.write_client.save_objects(index_name=idx_name, objects=objects)
        logger.info(f"Indexed {len(objects)} objects into Algolia index '{idx_name}'.")
        return [response]

    def search(
        self, query: str, entity_type: Optional[str] = None, limit: int = 10, index_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        idx_name = index_name or self.index_name
        filters = f"entity_type:{entity_type}" if entity_type else None

        search_params = SearchParamsObject(query=query, hits_per_page=limit, filters=filters)
        response = self.search_client.search_single_index(index_name=idx_name, search_params=search_params)

        results = []
        if hasattr(response, "hits"):
            for hit in response.hits:
                if hasattr(hit, "to_dict"):
                    results.append(hit.to_dict())
                elif isinstance(hit, dict):
                    results.append(hit)
                else:
                    results.append({"objectID": getattr(hit, "object_id", ""), "data": str(hit)})
        return results

    def seed_all_entities(self) -> Dict[str, int]:
        settings = get_settings()
        objects: List[Dict[str, Any]] = []

        # 1. Datasets
        datasets = settings.list_available_datasets()
        for ds in datasets:
            objects.append(
                {
                    "objectID": f"dataset_{ds['key']}",
                    "entity_type": "dataset",
                    "key": ds["key"],
                    "name": ds["name"],
                    "path": ds["path"],
                    "format": ds["format"],
                    "size_mb": ds["size_mb"],
                    "description": f"Dataset {ds['name']} stored at {ds['path']}",
                }
            )

        # 2. Quality Rules (from DuckDB if present)
        try:
            db = get_db()
            rules = db.execute("SELECT id, rule_name, rule_type, rule_expression, status FROM quality_rules")
            for r in rules:
                objects.append(
                    {
                        "objectID": f"rule_{r[0]}",
                        "entity_type": "rule",
                        "rule_id": r[0],
                        "rule_name": r[1],
                        "type": r[2],
                        "expression": r[3],
                        "description": f"Quality rule '{r[1]}' ({r[2]}): {r[3]}",
                        "status": r[4],
                    }
                )
        except Exception as e:
            logger.warning(f"Could not load quality rules for seeding: {e}")

        # 3. Alerts (from alert_service)
        try:
            from src.services.alerting import alert_service
            alerts = alert_service.get_alerts()
            for a in alerts:
                objects.append(
                    {
                        "objectID": f"alert_{a.alert_id}",
                        "entity_type": "alert",
                        "alert_id": a.alert_id,
                        "title": a.title,
                        "message": a.message,
                        "severity": a.severity,
                        "status": a.status,
                    }
                )
        except Exception as e:
            logger.warning(f"Could not load alerts for seeding: {e}")

        # 4. Audit Logs
        try:
            db = get_db()
            logs = db.execute("SELECT id, action, actor, target_table, details FROM audit_log ORDER BY id DESC LIMIT 50")
            for l in logs:
                objects.append(
                    {
                        "objectID": f"audit_{l[0]}",
                        "entity_type": "audit",
                        "audit_id": str(l[0]),
                        "action": l[1],
                        "actor": l[2],
                        "target_table": l[3],
                        "details": l[4],
                    }
                )
        except Exception as e:
            logger.warning(f"Could not load audit logs for seeding: {e}")

        self.index_entities(objects)
        return {
            "total_indexed": len(objects),
            "datasets": len(datasets),
        }


algolia_search_service = AlgoliaSearchService()
