# Graph DB Specialist — Data Infrastructure & Engineering

Production-ready graph data infrastructure with Neo4j/AWS Neptune, ETL pipelines, and query optimization framework.

## Architecture
Graph ETL pipeline: RDBMS/APIs/CSV/S3 → Python/Airflow ETL layer → Neo4j or AWS Neptune → FastAPI application layer.

## Data Sources
| Source | Type | Fields |
|--------|------|--------|
| PostgreSQL/MySQL | RDBMS | Nodes + relationships |
| REST APIs | JSON | Graph entities |
| CSV/JSON exports | File | Bulk import |
| S3/GCS | Object store | Large dataset ingest |

## Data Model
Property graph with node labels (Entity, Relationship, Source) and typed edges (SUPPLIES, ASSEMBLES_INTO, STORES).
Pydantic models enforce schema on ingest. Watermark-based CDC for incremental updates.

## CLI Reference
```bash
# Run ETL pipeline
python -m etl.etl_framework --source postgres --target neo4j

# Start FastAPI server
uvicorn api.main:app --host 0.0.0.0 --port 8000

# Run query optimizer
python -m query_optimization.optimizer --query "MATCH (a)-[r]->(b) RETURN a, r, b"
```

## Installation
```bash
pip install -r requirements.txt
cp .env.example .env  # configure Neo4j/Neptune credentials
python -m etl.etl_framework  # run ETL
```

## Quality Guarantees
- Watermark-based CDC prevents duplicate nodes on re-run
- Pydantic validation rejects malformed nodes/edges before load
- Query parameterization prevents Cypher injection
- Field-level encryption for PII in node properties

## Output Format
- Neo4j: Cypher MERGE statements
- Neptune: Gremlin traversal objects
- API: JSON with schema validated by Pydantic

## Project Structure
```
graph_db/models.py           # Node/Relationship Pydantic models
etl/etl_framework.py        # ETL pipeline orchestration
query_optimization/optimizer.py  # Cypher/Gremlin optimization
security/security.py         # Encryption + auth
api/main.py                  # FastAPI graph endpoints
```

## Limitations
- No real-time streaming (Kafka/Kinesis not in scope)
- No ML on graph data (node embeddings/GNNs)
- No mobile app development
