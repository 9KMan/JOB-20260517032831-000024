from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from typing import Dict, Any
import logging
from datetime import datetime

from api.schemas import (
    NodeCreate,
    RelationshipCreate,
    QueryRequest,
    ShortestPathRequest,
    PipelineTriggerRequest,
    HealthResponse
)
from graph_db.models import GraphNode, GraphRelationship

logger = logging.getLogger(__name__)

neo4j_loader = None
neptune_loader = None
query_cache = None
query_registry = None
pipeline_runs: Dict[str, Any] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Graph Database API")
    yield
    logger.info("Shutting down Graph Database API")


app = FastAPI(
    title="Graph Database Specialist API",
    description="Data Infrastructure & Engineering API for Neo4j/AWS Neptune",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(status="healthy", timestamp=datetime.utcnow())


@app.post("/graph/node")
async def create_node(node: NodeCreate):
    try:
        node_data = GraphNode(
            id=node.properties.get("id", ""),
            label=node.label,
            properties=node.properties
        )
        if neo4j_loader:
            neo4j_loader.load_nodes([node_data])
        return {"status": "created", "node_id": node_data.id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/graph/edge")
async def create_relationship(rel: RelationshipCreate):
    try:
        rel_data = GraphRelationship(
            id=f"{rel.from_id}_{rel.to_id}",
            type=rel.type,
            from_id=rel.from_id,
            to_id=rel.to_id,
            properties=rel.properties
        )
        if neo4j_loader:
            neo4j_loader.load_relationships([rel_data])
        return {"status": "created", "relationship_id": rel_data.id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/graph/query")
async def run_query(req: QueryRequest):
    from query_optimization import QueryOptimizer, ParameterizedQuery, QueryLanguage
    optimizer = QueryOptimizer()
    is_valid, error = optimizer.validate_query(req.query, QueryLanguage.CYPHER if req.language == "cypher" else QueryLanguage.GREMLIN)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error)
    query, params = ParameterizedQuery.build(req.query, req.params, QueryLanguage.CYPHER if req.language == "cypher" else QueryLanguage.GREMLIN)
    try:
        if neo4j_loader:
            result = neo4j_loader.execute_query(query, params)
            return {"results": result}
        return {"results": [], "message": "No graph database connected"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/graph/shortest-path")
async def shortest_path(req: ShortestPathRequest):
    if not neo4j_loader:
        raise HTTPException(status_code=503, detail="No database connected")
    try:
        query = """
        MATCH path = shortestPath((a {id: $from_id})-[*..$max_depth]-(b {id: $to_id}))
        RETURN path
        """
        result = neo4j_loader.execute_query(query, {"from_id": req.from_id, "to_id": req.to_id, "max_depth": req.max_depth})
        return {"path": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/pipeline/trigger")
async def trigger_pipeline(req: PipelineTriggerRequest):
    run_id = f"run_{datetime.utcnow().timestamp()}"
    pipeline_runs[run_id] = {
        "run_id": run_id,
        "pipeline_name": req.pipeline_name,
        "status": "running",
        "started_at": datetime.utcnow()
    }
    return {"run_id": run_id, "status": "triggered"}


@app.get("/pipeline/status/{run_id}")
async def get_pipeline_status(run_id: str):
    if run_id not in pipeline_runs:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    return pipeline_runs[run_id]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)