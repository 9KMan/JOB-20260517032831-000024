from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import logging
from datetime import datetime
import json

from graph_db.models import GraphNode, GraphRelationship, Watermark, PipelineRun

logger = logging.getLogger(__name__)


class DataSource(ABC):
    @abstractmethod
    def extract(self, watermark: Optional[Watermark] = None) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_watermark(self) -> Watermark:
        pass


class RDBMSConnector(DataSource):
    def __init__(self, connection_string: str, table_name: str, id_column: str = "id"):
        self.connection_string = connection_string
        self.table_name = table_name
        self.id_column = id_column
        self._last_watermark = None

    def extract(self, watermark: Optional[Watermark] = None) -> List[Dict[str, Any]]:
        import psycopg2
        conn = psycopg2.connect(self.connection_string)
        cursor = conn.cursor()
        query = f"SELECT * FROM {self.table_name}"
        if watermark:
            query += f" WHERE updated_at > '{watermark.last_updated.isoformat()}'"
        cursor.execute(query)
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        conn.close()
        return [dict(zip(columns, row)) for row in rows]

    def get_watermark(self) -> Watermark:
        return Watermark(
            source_id=self.table_name,
            last_updated=datetime.utcnow(),
            checkpoint=f"wm_{self.table_name}"
        )


class RESTAPISource(DataSource):
    def __init__(self, base_url: str, endpoint: str, auth_token: Optional[str] = None):
        self.base_url = base_url
        self.endpoint = endpoint
        self.auth_token = auth_token

    def extract(self, watermark: Optional[Watermark] = None) -> List[Dict[str, Any]]:
        import httpx
        headers = {"Authorization": f"Bearer {self.auth_token}"} if self.auth_token else {}
        url = f"{self.base_url}/{self.endpoint}"
        response = httpx.get(url, headers=headers, timeout=30.0)
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, list) else [data]

    def get_watermark(self) -> Watermark:
        return Watermark(
            source_id=self.endpoint,
            last_updated=datetime.utcnow(),
            checkpoint=f"wm_{self.endpoint}"
        )


class CSVFileSource(DataSource):
    def __init__(self, file_path: str):
        self.file_path = file_path

    def extract(self, watermark: Optional[Watermark] = None) -> List[Dict[str, Any]]:
        import pandas as pd
        df = pd.read_csv(self.file_path)
        return df.to_dict(orient="records")

    def get_watermark(self) -> Watermark:
        return Watermark(
            source_id=self.file_path,
            last_updated=datetime.utcnow(),
            checkpoint=f"wm_file_{self.file_path}"
        )


class S3Source(DataSource):
    def __init__(self, bucket: str, key: str, aws_profile: Optional[str] = None):
        self.bucket = bucket
        self.key = key
        self.aws_profile = aws_profile

    def extract(self, watermark: Optional[Watermark] = None) -> List[Dict[str, Any]]:
        import boto3
        import pandas as pd
        session = boto3.Session(profile_name=self.aws_profile) if self.aws_profile else boto3.Session()
        s3 = session.client("s3")
        obj = s3.get_object(Bucket=self.bucket, Key=self.key)
        if self.key.endswith(".csv"):
            df = pd.read_csv(obj["Body"])
            return df.to_dict(orient="records")
        elif self.key.endswith(".json"):
            body = obj["Body"].read().decode("utf-8")
            return json.loads(body)
        return []

    def get_watermark(self) -> Watermark:
        return Watermark(
            source_id=f"s3://{self.bucket}/{self.key}",
            last_updated=datetime.utcnow(),
            checkpoint=f"wm_s3_{self.key}"
        )


class GraphTransformer:
    @staticmethod
    def relational_to_graph(
        records: List[Dict[str, Any]],
        node_label: str,
        id_field: str,
        property_mappings: Dict[str, str]
    ) -> List[GraphNode]:
        nodes = []
        for record in records:
            props = {new_key: record[old_key] for old_key, new_key in property_mappings.items() if old_key in record}
            node = GraphNode(
                id=str(record[id_field]),
                label=node_label,
                properties=props
            )
            nodes.append(node)
        return nodes

    @staticmethod
    def build_relationships(
        records: List[Dict[str, Any]],
        rel_type: str,
        from_field: str,
        to_field: str,
        property_mappings: Dict[str, str]
    ) -> List[GraphRelationship]:
        relationships = []
        for record in records:
            props = {new_key: record[old_key] for old_key, new_key in property_mappings.items() if old_key in record}
            rel = GraphRelationship(
                id=f"{record[from_field]}_{record[to_field]}",
                type=rel_type,
                from_id=str(record[from_field]),
                to_id=str(record[to_field]),
                properties=props
            )
            relationships.append(rel)
        return relationships


class Neo4jLoader:
    def __init__(self, uri: str, username: str, password: str, database: str = "neo4j"):
        self.uri = uri
        self.username = username
        self.password = password
        self.database = database

    def load_nodes(self, nodes: List[GraphNode]) -> None:
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(self.uri, auth=(self.username, self.password))
        with driver.session(database=self.database) as session:
            for node in nodes:
                cypher = node.to_cypher_merge()
                session.run(cypher)
        driver.close()

    def load_relationships(self, relationships: List[GraphRelationship]) -> None:
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(self.uri, auth=(self.username, self.password))
        with driver.session(database=self.database) as session:
            for rel in relationships:
                cypher = rel.to_cypher_merge()
                session.run(cypher)
        driver.close()

    def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(self.uri, auth=(self.username, self.password))
        with driver.session(database=self.database) as session:
            result = session.run(query, parameters=params or {})
            return [dict(record) for record in result]


class NeptuneLoader:
    def __init__(self, endpoint: str, region: str = "us-east-1"):
        self.endpoint = endpoint
        self.region = region

    def load_nodes(self, nodes: List[GraphNode]) -> None:
        from gremlin_python.driver import client
        conn = client.Client(self.endpoint, "g")
        for node in nodes:
            conn.submit(
                f"g.addV('{node.label.value}').property('id', '{node.id}')"
            )
        conn.close()

    def execute_gremlin(self, traversal: str) -> List[Any]:
        from gremlin_python.driver import client
        conn = client.Client(self.endpoint, "g")
        result = conn.submit(traversal)
        conn.close()
        return result.all().result()