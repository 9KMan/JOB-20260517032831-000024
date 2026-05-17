import re
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class QueryLanguage(str, Enum):
    CYPHER = "cypher"
    GREMLIN = "gremlin"


@dataclass
class QueryProfile:
    query: str
    language: QueryLanguage
    planning_time_ms: float
    execution_time_ms: float
    rows_returned: int
    hits_per_page: int
    page_cache_hit_ratio: float
    operators: List[str]


class CypherExplainParser:
    @staticmethod
    def parse(explain_output: Dict[str, Any]) -> QueryProfile:
        profile = QueryProfile(
            query="",
            language=QueryLanguage.CYPHER,
            planning_time_ms=0.0,
            execution_time_ms=0.0,
            rows_returned=0,
            hits_per_page=0,
            page_cache_hit_ratio=0.0,
            operators=[]
        )
        if "profile" in explain_output:
            profile.execution_time_ms = explain_output["profile"].get("executionTime", 0.0)
            profile.rows_returned = explain_output["profile"].get("rows", 0)
        if "planner" in explain_output:
            profile.planning_time_ms = explain_output["planner"].get("plannerTime", 0.0)
        if "runtime" in explain_output:
            profile.operators = [op.get("operator", "") for op in explain_output.get("operators", [])]
        return profile


class GremlinExplainParser:
    @staticmethod
    def parse(profile_output: Dict[str, Any]) -> QueryProfile:
        profile = QueryProfile(
            query="",
            language=QueryLanguage.GREMLIN,
            planning_time_ms=0.0,
            execution_time_ms=0.0,
            rows_returned=0,
            hits_per_page=0,
            page_cache_hit_ratio=0.0,
            operators=[]
        )
        if "metrics" in profile_output:
            for metric in profile_output["metrics"]:
                profile.execution_time_ms += metric.get("time", 0)
                profile.operators.append(metric.get("name", ""))
        return profile


class QueryOptimizer:
    def __init__(self):
        self.query_cache: Dict[str, Tuple[str, float]] = {}
        self.cache_ttl_seconds: int = 300

    def validate_query(self, query: str, language: QueryLanguage) -> Tuple[bool, Optional[str]]:
        if language == QueryLanguage.CYPHER:
            dangerous = ["DROP", "DELETE", "REMOVE", "DETACH DELETE"]
            for kw in dangerous:
                if re.search(rf"\b{kw}\b", query, re.IGNORECASE):
                    return False, f"Forbidden keyword: {kw}"
            return True, None
        return True, None

    def suggest_indexes(self, query: str, language: QueryLanguage) -> List[str]:
        indexes = []
        if language == QueryLanguage.CYPHER:
            label_matches = re.findall(r":(\w+)", query)
            for label in label_matches:
                indexes.append(f"CREATE INDEX FOR (n:{label}) ON (n.id)")
            property_matches = re.findall(r"\.(\w+)\s*=", query)
            for prop in property_matches:
                indexes.append(f"CREATE INDEX FOR (n) ON (n.{prop})")
        return indexes


class QueryCache:
    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url
        self._client = None

    def get(self, key: str) -> Optional[Any]:
        if not self.redis_url:
            return None
        try:
            import redis
            if self._client is None:
                self._client = redis.from_url(self.redis_url)
            return self._client.get(key)
        except Exception:
            return None

    def set(self, key: str, value: Any, ttl: int = 300) -> None:
        if not self.redis_url:
            return
        try:
            import redis
            if self._client is None:
                self._client = redis.from_url(self.redis_url)
            self._client.setex(key, ttl, value)
        except Exception:
            pass


class ParameterizedQuery:
    @staticmethod
    def build(query: str, params: Dict[str, Any], language: QueryLanguage) -> Tuple[str, Dict[str, Any]]:
        if language == QueryLanguage.CYPHER:
            cypher_params = {}
            for i, (key, value) in enumerate(params.items()):
                param_key = f"param_{i}"
                cypher_params[param_key] = value
                query = query.replace(f"${key}", f"${param_key}")
            return query, cypher_params
        return query, params


class QueryRegistry:
    def __init__(self):
        self._queries: Dict[str, str] = {}

    def register(self, name: str, query: str, language: QueryLanguage) -> None:
        self._queries[name] = query

    def get(self, name: str) -> Optional[str]:
        return self._queries.get(name)

    def list_queries(self) -> List[str]:
        return list(self._queries.keys())