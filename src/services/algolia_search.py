import logging
from typing import Any, Dict, List, Optional
from src.config import get_settings
from src.db.connection import get_db

logger = logging.getLogger(__name__)


class AlgoliaSearchService:
    """
    Search & Catalog Service connected to Algolia Search API,
    with automatic DuckDB Full-Text Search fallback when Algolia keys are unset.
    """

    def __init__(self):
        settings = get_settings()
        self.app_id = getattr(settings, "algolia_app_id", None)
        self.write_key = getattr(settings, "algolia_write_key", None)
        self.search_key = getattr(settings, "algolia_search_key", None)
        self.index_name = "datatrust_entities"

        self._write_client = None
        self._search_client = None

    @property
    def has_credentials(self) -> bool:
        return bool(self.app_id and (self.write_key or self.search_key))

    @property
    def write_client(self):
        if self._write_client is None:
            if not self.has_credentials:
                return None
            try:
                from algoliasearch.search.client import SearchClientSync
                self._write_client = SearchClientSync(self.app_id, self.write_key)
            except Exception as e:
                logger.warning(f"Could not initialize Algolia write client: {e}")
        return self._write_client

    @property
    def search_client(self):
        if self._search_client is None:
            if not self.has_credentials:
                return None
            try:
                from algoliasearch.search.client import SearchClientSync
                key = self.search_key or self.write_key
                self._search_client = SearchClientSync(self.app_id, key)
            except Exception as e:
                logger.warning(f"Could not initialize Algolia search client: {e}")
        return self._search_client

    def index_entities(self, objects: List[Dict[str, Any]], index_name: Optional[str] = None) -> List[Any]:
        if not objects:
            return []
        idx_name = index_name or self.index_name
        if self.write_client:
            try:
                response = self.write_client.save_objects(index_name=idx_name, objects=objects)
                logger.info(f"Indexed {len(objects)} objects into Algolia index '{idx_name}'.")
                return [response]
            except Exception as e:
                logger.warning(f"Algolia indexing failed: {e}")
        return []

    def search(
        self, query: str, entity_type: Optional[str] = None, limit: int = 10, index_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Searches via Algolia if configured; falls back to DuckDB search."""
        idx_name = index_name or self.index_name

        if self.search_client:
            try:
                from algoliasearch.search.models import SearchParamsObject
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
            except Exception as e:
                logger.warning(f"Algolia search failed, falling back to DuckDB: {e}")

        # DuckDB fallback search
        return self._fallback_search(query=query, entity_type=entity_type, limit=limit)

    def _fallback_search(
        self, query: str, entity_type: Optional[str] = None, limit: int = 10
    ) -> List[Dict[str, Any]]:
        settings = get_settings()
        q_lower = query.lower()
        results: List[Dict[str, Any]] = []

        # 1. Search Datasets
        if not entity_type or entity_type == "dataset":
            for ds in settings.list_available_datasets():
                if q_lower in ds["name"].lower() or q_lower in ds["key"].lower():
                    results.append({
                        "objectID": f"dataset_{ds['key']}",
                        "entity_type": "dataset",
                        "name": ds["name"],
                        "key": ds["key"],
                        "path": ds["path"],
                        "size_mb": ds["size_mb"],
                        "description": f"Dataset {ds['name']}",
                    })

        # 2. Search Rules
        if not entity_type or entity_type == "rule":
            try:
                db = get_db()
                rules = db.execute(
                    """
                    SELECT id, rule_name, rule_type, rule_expression, status
                    FROM quality_rules
                    WHERE LOWER(rule_name) LIKE ? OR LOWER(rule_expression) LIKE ?
                    LIMIT ?
                    """,
                    [f"%{q_lower}%", f"%{q_lower}%", limit]
                )
                for r in rules:
                    results.append({
                        "objectID": f"rule_{r[0]}",
                        "entity_type": "rule",
                        "rule_id": r[0],
                        "rule_name": r[1],
                        "type": r[2],
                        "expression": r[3],
                        "status": r[4],
                    })
            except Exception:
                pass

        # 3. Search Audit Log
        if not entity_type or entity_type == "audit":
            try:
                db = get_db()
                logs = db.execute(
                    """
                    SELECT id, action, actor, target_table, details
                    FROM audit_log
                    WHERE LOWER(action) LIKE ? OR LOWER(target_table) LIKE ?
                    LIMIT ?
                    """,
                    [f"%{q_lower}%", f"%{q_lower}%", limit]
                )
                for l in logs:
                    results.append({
                        "objectID": f"audit_{l[0]}",
                        "entity_type": "audit",
                        "action": l[1],
                        "actor": l[2],
                        "target_table": l[3],
                        "details": l[4],
                    })
            except Exception:
                pass

        return results[:limit]

    def seed_all_entities(self) -> Dict[str, int]:
        settings = get_settings()
        objects: List[Dict[str, Any]] = []

        # 1. Datasets
        datasets = settings.list_available_datasets()
        for ds in datasets:
            objects.append({
                "objectID": f"dataset_{ds['key']}",
                "entity_type": "dataset",
                "key": ds["key"],
                "name": ds["name"],
                "path": ds["path"],
                "format": ds["format"],
                "size_mb": ds["size_mb"],
                "description": f"Dataset {ds['name']} stored at {ds['path']}",
            })

        # 2. Quality Rules
        try:
            db = get_db()
            rules = db.execute("SELECT id, rule_name, rule_type, rule_expression, status FROM quality_rules")
            for r in rules:
                objects.append({
                    "objectID": f"rule_{r[0]}",
                    "entity_type": "rule",
                    "rule_id": r[0],
                    "rule_name": r[1],
                    "type": r[2],
                    "expression": r[3],
                    "description": f"Quality rule '{r[1]}' ({r[2]}): {r[3]}",
                    "status": r[4],
                })
        except Exception as e:
            logger.warning(f"Could not load quality rules for seeding: {e}")

        self.index_entities(objects)
        return {
            "total_indexed": len(objects),
            "datasets": len(datasets),
        }


algolia_search_service = AlgoliaSearchService()
