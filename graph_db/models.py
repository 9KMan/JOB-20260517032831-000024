from enum import Enum
from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field


class NodeLabel(str, Enum):
    SOURCE = "Source"
    ENTITY = "Entity"
    RELATIONSHIP = "Relationship"
    SUPPLIER = "Supplier"
    COMPONENT = "Component"
    PRODUCT = "Product"
    WAREHOUSE = "Warehouse"


class RelationshipType(str, Enum):
    SUPPLIES = "SUPPLIES"
    ASSEMBLES_INTO = "ASSEMBLES_INTO"
    STORES = "STORES"
    HAS_RELATIONSHIP = "HAS_RELATIONSHIP"


class GraphNode(BaseModel):
    id: str
    label: NodeLabel
    properties: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    def to_cypher_merge(self) -> str:
        props = ", ".join([f"{k}: '{v}'" for k, v in self.properties.items()])
        return f"MERGE (n:{self.label.value} {{id: '{self.id}'}}) SET n += {{{props}}}"


class GraphRelationship(BaseModel):
    id: str
    type: RelationshipType
    from_id: str
    to_id: str
    properties: Dict[str, Any] = Field(default_factory=dict)
    weight: Optional[float] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    def to_cypher_merge(self) -> str:
        props = ", ".join([f"{k}: '{v}'" for k, v in self.properties.items()])
        return (
            f"MATCH (a {{id: '{self.from_id}'}}), (b {{id: '{self.to_id}'}}) "
            f"MERGE (a)-[r:{self.type.value} {{id: '{self.id}'}}]->(b) "
            f"SET r += {{{props}}}"
        )


class Watermark(BaseModel):
    source_id: str
    last_updated: datetime
    checkpoint: str


class PipelineRun(BaseModel):
    run_id: str
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    records_processed: int = 0
    errors: List[str] = Field(default_factory=list)


class SupplyChainNode(GraphNode):
    label: NodeLabel = NodeLabel.SUPPLIER

    model_config = {"populate_by_name": True}


class SupplyChainRelationship(GraphRelationship):
    type: RelationshipType = RelationshipType.SUPPLIES

    model_config = {"populate_by_name": True}