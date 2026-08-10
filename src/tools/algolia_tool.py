from typing import Any, Dict, Optional
from src.tools.base import BaseTool
from src.services.algolia_search import algolia_search_service


class AlgoliaSearchTool(BaseTool):
    name = "algolia_search"
    description = "Search across enterprise Datasets, Quality Rules, Alerts, and Audit Logs using Algolia full-text search."
    input_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search term or phrase"},
            "entity_type": {
                "type": "string",
                "description": "Optional filter for entity type (dataset, rule, alert, audit)",
                "enum": ["dataset", "rule", "alert", "audit"],
            },
            "limit": {"type": "integer", "description": "Maximum number of search results to return", "default": 10},
        },
        "required": ["query"],
    }

    def execute(self, input_data: dict) -> dict:
        query = input_data.get("query", "")
        entity_type = input_data.get("entity_type")
        limit = input_data.get("limit", 10)

        if not query:
            return {"error": "Query string is required", "hits": []}

        try:
            hits = algolia_search_service.search(query=query, entity_type=entity_type, limit=limit)
            return {
                "query": query,
                "entity_type": entity_type,
                "count": len(hits),
                "hits": hits,
            }
        except Exception as e:
            return {"error": str(e), "hits": []}
