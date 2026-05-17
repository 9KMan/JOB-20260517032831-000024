from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum
from pydantic import BaseModel

from graph_db.models import GraphNode, GraphRelationship, NodeLabel, RelationshipType


class NodeCreate(BaseModel):
    label: str
    properties: Dict[str, Any]


class RelationshipCreate(BaseModel):
    type: str
    from_id: str
    to_id: str
    properties: Dict[str, Any] = {}


class QueryRequest(BaseModel):
    query: str
    language: str = "cypher"
    params: Dict[str, Any] = {}


class ShortestPathRequest(BaseModel):
    from_id: str
    to_id: str
    max_depth: int = 10


class PipelineTriggerRequest(BaseModel):
    pipeline_name: str
    config: Dict[str, Any] = {}


class HealthResponse(BaseModel):
    status: str
    timestamp: datetime
    version: str = "1.0.0"