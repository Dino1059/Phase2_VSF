from typing import Dict, Any, Iterable, List, Optional


class JurisdictionHierarchyConfig:
    """
    Config-driven Jurisdiction Hierarchy Resolver.
    Resolves Global -> Zone -> Country without hardcoding.
    """

    DEFAULT_MAPPING = {
        "VN": {
            "default_country": "VN",
            "supported_countries": ["VN"]
        },
        "EU": {
            "default_country": "DE",
            "supported_countries": ["DE", "FR", "NL", "IT", "ES", "BE"]
        },
        "US": {
            "default_country": "US-CA",
            "supported_countries": ["US-NY", "US-CA", "US-TX", "US-FL", "US-MI"]
        }
    }

    ZONE_ALIASES = {
        "GLOBAL": "GLOBAL",
        "WORLDWIDE": "GLOBAL",
        "VN": "VN",
        "VIETNAM": "VN",
        "VIET NAM": "VN",
        "EU": "EU",
        "EEA": "EU",
        "EUROPEAN UNION": "EU",
        "US": "US",
        "USA": "US",
        "UNITED STATES": "US",
    }

    def __init__(self, mapping: Optional[Dict[str, Any]] = None):
        # Copy nested values so callers/cache refreshes cannot mutate defaults.
        source = mapping if mapping is not None else self.DEFAULT_MAPPING
        self.mapping = self._normalize_mapping(source)

    @classmethod
    def from_rows(cls, rows: Iterable[Dict[str, Any]]) -> "JurisdictionHierarchyConfig":
        """Build the hierarchy from DB/API rows without coupling to a DB client.

        Accepted rows use ``code``/``jurisdiction_code``, ``parent_code`` and
        optional ``is_default``. Zone rows have parent GLOBAL; child rows have
        their zone as parent. Invalid/incomplete input safely falls back to the
        built-in three-zone hierarchy.
        """
        materialized = [dict(row) for row in rows]
        zones: Dict[str, Dict[str, Any]] = {}
        for row in materialized:
            code = cls.normalize_zone(row.get("code") or row.get("jurisdiction_code"))
            parent = cls.normalize_zone(row.get("parent_code") or row.get("parent"))
            if code != "GLOBAL" and parent == "GLOBAL":
                zones.setdefault(code, {"default_country": code, "supported_countries": [code]})
        for row in materialized:
            code = cls.normalize_zone(row.get("code") or row.get("jurisdiction_code"))
            parent = cls.normalize_zone(row.get("parent_code") or row.get("parent"))
            if parent in zones and code not in {"GLOBAL", parent}:
                zones[parent]["supported_countries"].append(code)
                if row.get("is_default") or row.get("default_for_parent"):
                    zones[parent]["default_country"] = code
        return cls(zones or None)

    @classmethod
    def _normalize_mapping(cls, source: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        result: Dict[str, Dict[str, Any]] = {}
        for raw_zone, raw_config in source.items():
            zone = cls.normalize_zone(raw_zone)
            if zone == "GLOBAL" or not isinstance(raw_config, dict):
                continue
            countries = [
                cls.normalize_zone(item)
                for item in raw_config.get("supported_countries", [])
                if item
            ]
            default = cls.normalize_zone(raw_config.get("default_country") or zone)
            if default not in countries:
                countries.append(default)
            result[zone] = {
                "default_country": default,
                "supported_countries": list(dict.fromkeys(countries)),
            }
        return result

    @classmethod
    def normalize_zone(cls, zone: Optional[str]) -> str:
        """Return the canonical policy-zone code used by rules and findings."""
        if zone is None or not str(zone).strip():
            return "GLOBAL"
        candidate = " ".join(str(zone).strip().upper().replace("_", "-").split())
        return cls.ZONE_ALIASES.get(candidate, candidate)

    def resolve_chain(self, zone: Optional[str], country: Optional[str] = None) -> List[str]:
        """
        Returns list of applicable jurisdictions from global down to country:
        ['GLOBAL', zone, country]
        """
        chain = ["GLOBAL"]
        normalized_zone = self.normalize_zone(zone)

        if normalized_zone in self.mapping:
            chain.append(normalized_zone)
            zone_cfg = self.mapping[normalized_zone]
            
            # US is the product's US-CA legal scope, so the zone alias must
            # resolve to California. Other zones only add a country when the
            # record explicitly supplies it.
            resolved_country = zone_cfg.get("default_country") if normalized_zone == "US" else None
            if country:
                cand = self.normalize_zone(country)
                if cand in zone_cfg.get("supported_countries", []):
                    resolved_country = cand

            if resolved_country and resolved_country != normalized_zone:
                chain.append(resolved_country)
        elif normalized_zone != "GLOBAL":
            chain.append(normalized_zone)
            if country and country != normalized_zone:
                chain.append(str(country).strip().upper())

        return chain

    def is_known_zone(self, zone: Optional[str]) -> bool:
        return self.normalize_zone(zone) in self.mapping
