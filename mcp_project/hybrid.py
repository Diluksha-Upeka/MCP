"""
Hybrid retrieval helpers for vector + graph backends.
"""
import os
import json
import sqlite3
import hashlib
from typing import Any

from neo4j import GraphDatabase
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from db import DB_PATH

VECTOR_DIM = int(os.getenv("MCP_VECTOR_DIM", "64"))
QDRANT_COLLECTION = os.getenv("MCP_QDRANT_COLLECTION", "sops")


def _embed_text(text: str, dim: int = VECTOR_DIM) -> list[float]:
    """Deterministic embedding for demo purposes."""
    text = (text or "").strip().lower()
    if not text:
        return [0.0] * dim
    chunks = []
    seed = text.encode("utf-8")
    while len(chunks) < dim:
        seed = hashlib.sha256(seed).digest()
        chunks.extend([((b / 255.0) * 2.0) - 1.0 for b in seed])
    return chunks[:dim]


def _get_qdrant_client() -> QdrantClient | None:
    url = os.getenv("QDRANT_URL", "").strip()
    if not url:
        return None
    api_key = os.getenv("QDRANT_API_KEY", "").strip() or None
    return QdrantClient(url=url, api_key=api_key)


def _get_neo4j_driver() -> GraphDatabase.driver | None:
    uri = os.getenv("NEO4J_URI", "").strip()
    user = os.getenv("NEO4J_USER", "").strip()
    password = os.getenv("NEO4J_PASSWORD", "").strip()
    if not (uri and user and password):
        return None
    return GraphDatabase.driver(uri, auth=(user, password))


def ensure_qdrant_collection(client: QdrantClient) -> None:
    collections = client.get_collections().collections
    exists = any(col.name == QDRANT_COLLECTION for col in collections)
    if not exists:
        client.create_collection(
            collection_name=QDRANT_COLLECTION,
            vectors_config=qmodels.VectorParams(size=VECTOR_DIM, distance=qmodels.Distance.COSINE)
        )


def _load_sops_from_sqlite() -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, title, department, owner, status, content, updated_at FROM sops")
    rows = cur.fetchall()
    conn.close()
    return [
        {
            "id": r[0],
            "title": r[1],
            "department": r[2],
            "owner": r[3],
            "status": r[4],
            "content": r[5],
            "updated_at": r[6]
        }
        for r in rows
    ]


def upsert_sops_vectors() -> dict:
    client = _get_qdrant_client()
    if not client:
        return {"status": "error", "message": "QDRANT_URL is not configured."}

    ensure_qdrant_collection(client)
    sops = _load_sops_from_sqlite()
    points = []
    for sop in sops:
        vector = _embed_text(f"{sop['title']} {sop['content']}")
        payload = {
            "sop_id": sop["id"],
            "title": sop["title"],
            "department": sop["department"],
            "owner": sop["owner"],
            "status": sop["status"],
            "updated_at": sop["updated_at"],
        }
        points.append(qmodels.PointStruct(id=sop["id"], vector=vector, payload=payload))

    client.upsert(collection_name=QDRANT_COLLECTION, points=points)
    return {"status": "success", "count": len(points)}


def search_sops_vector(query: str, limit: int = 10) -> list[dict]:
    client = _get_qdrant_client()
    if not client:
        return []

    vector = _embed_text(query)
    results = client.search(
        collection_name=QDRANT_COLLECTION,
        query_vector=vector,
        limit=limit
    )
    return [
        {
            "score": hit.score,
            "sop_id": hit.payload.get("sop_id"),
            "title": hit.payload.get("title"),
            "department": hit.payload.get("department"),
            "owner": hit.payload.get("owner"),
            "status": hit.payload.get("status"),
            "updated_at": hit.payload.get("updated_at")
        }
        for hit in results
    ]


def query_graph_entities(query: str, limit: int = 10) -> list[dict]:
    driver = _get_neo4j_driver()
    if not driver:
        return []
    cypher = (
        "MATCH (n) WHERE toLower(n.name) CONTAINS toLower($q) "
        "RETURN n.sqlite_id AS id, labels(n) AS labels, n.name AS name, n AS props "
        "LIMIT $limit"
    )
    with driver.session() as session:
        records = session.run(cypher, q=query, limit=limit)
        return [
            {
                "id": record["id"],
                "labels": record["labels"],
                "name": record["name"],
                "properties": dict(record["props"])
            }
            for record in records
        ]


def query_graph_edges(entity_id: int, limit: int = 10) -> list[dict]:
    driver = _get_neo4j_driver()
    if not driver:
        return []
    cypher = (
        "MATCH (a {sqlite_id: $id})-[r]-(b) "
        "RETURN id(r) AS id, type(r) AS type, a.sqlite_id AS from_id, b.sqlite_id AS to_id, r AS props "
        "LIMIT $limit"
    )
    with driver.session() as session:
        records = session.run(cypher, id=entity_id, limit=limit)
        return [
            {
                "id": record["id"],
                "type": record["type"],
                "from_id": record["from_id"],
                "to_id": record["to_id"],
                "properties": dict(record["props"])
            }
            for record in records
        ]


def upsert_graph_data() -> dict:
    driver = _get_neo4j_driver()
    if not driver:
        return {"status": "error", "message": "NEO4J_URI/NEO4J_USER/NEO4J_PASSWORD not configured."}

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, entity_type, name, attributes_json FROM graph_entities")
    entities = cur.fetchall()
    cur.execute("SELECT from_entity_id, to_entity_id, relation_type, attributes_json FROM graph_edges")
    edges = cur.fetchall()
    conn.close()

    with driver.session() as session:
        for ent in entities:
            props = json.loads(ent[3] or "{}")
            session.run(
                "MERGE (n {sqlite_id: $id}) SET n.name = $name, n.entity_type = $type SET n += $props",
                id=ent[0], name=ent[2], type=ent[1], props=props
            )
        for edge in edges:
            props = json.loads(edge[3] or "{}")
            session.run(
                "MATCH (a {sqlite_id: $from_id}), (b {sqlite_id: $to_id}) "
                "MERGE (a)-[r:RELATES_TO {relation_type: $rel}]->(b) SET r += $props",
                from_id=edge[0], to_id=edge[1], rel=edge[2], props=props
            )

    return {"status": "success", "entity_count": len(entities), "edge_count": len(edges)}
