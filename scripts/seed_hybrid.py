"""
Seed Neo4j + Qdrant with demo data from SQLite.
"""
from mcp_project.hybrid import upsert_sops_vectors, upsert_graph_data


def main() -> None:
    print("Seeding Qdrant vectors...")
    print(upsert_sops_vectors())
    print("Seeding Neo4j graph...")
    print(upsert_graph_data())


if __name__ == "__main__":
    main()
