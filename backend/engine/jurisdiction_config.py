from typing import Dict, Any, List, Optional
import os
import json


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
            "default_country": "US-NY",
            "supported_countries": ["US-NY", "US-CA", "US-TX", "US-FL", "US-MI"]
        }
    }

    def __init__(self, mapping: Optional[Dict[str, Any]] = None):
        self.mapping = mapping or dict(self.DEFAULT_MAPPING)

    def resolve_chain(self, zone: Optional[str], country: Optional[str] = None) -> List[str]:
        """
        Returns list of applicable jurisdictions from global down to country:
        ['GLOBAL', zone, country]
        """
        chain = ["GLOBAL"]
        normalized_zone = str(zone).strip().upper() if zone else "GLOBAL"

        if normalized_zone in self.mapping:
            chain.append(normalized_zone)
            zone_cfg = self.mapping[normalized_zone]
            
            resolved_country = None
            if country:
                cand = str(country).strip().upper()
                if cand in zone_cfg.get("supported_countries", []):
                    resolved_country = cand
                else:
                    resolved_country = cand
            else:
                resolved_country = zone_cfg.get("default_country", normalized_zone)

            if resolved_country and resolved_country != normalized_zone:
                chain.append(resolved_country)
        elif normalized_zone != "GLOBAL":
            chain.append(normalized_zone)
            if country and country != normalized_zone:
                chain.append(str(country).strip().upper())

        return chain
