"""Run investigation for hello.khan7684@gmail.com and verify results."""
import asyncio

INV_ID = "9f16f268-5b94-409c-b47a-b07ec8b29d1a"

async def main():
    # 1. Run the orchestrator directly (Celery isn't running)
    print("=== Running orchestrator for email investigation ===")
    from app.ai.client import get_llm_call_fn
    from app.services.orchestrator import run_investigation_loop

    result = await run_investigation_loop(INV_ID, llm_call_fn=get_llm_call_fn())
    print(f"  Status: {result.get('status')}")
    print(f"  Stop reason: {result.get('stop_reason')}")
    gs = result.get("graph_summary", {})
    print(f"  Graph entities: {gs.get('entity_count', 0)}")
    print(f"  Graph relationships: {gs.get('relationship_count', 0)}")

    # 2. Check PG counts
    print("\n=== PostgreSQL counts ===")
    from app.db.client import get_pool
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT entity_count, relationship_count, observation_count FROM investigations WHERE id = $1",
            INV_ID,
        )
        if row:
            print(f"  entity_count={row['entity_count']}, relationship_count={row['relationship_count']}, observation_count={row['observation_count']}")

    # 3. Check Neo4j graph
    print("\n=== Neo4j graph ===")
    from app.graph.reader import get_investigation_subgraph
    graph = await get_investigation_subgraph(INV_ID)
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    edge_list = edges.get("data", []) if isinstance(edges, dict) else edges
    print(f"  Nodes: {len(nodes)}, Edges: {len(edge_list)}")

    type_dist = {}
    for n in nodes:
        ntype = n.get("data", {}).get("type", "Unknown")
        type_dist[ntype] = type_dist.get(ntype, 0) + 1
    if type_dist:
        print("  Node types:")
        for t, c in sorted(type_dist.items(), key=lambda x: -x[1]):
            print(f"    {t}: {c}")

    # 4. Check observations
    print("\n=== Observations ===")
    async with pool.acquire() as conn:
        obs = await conn.fetch(
            "SELECT id, source_adapter, method, target, status FROM observations WHERE investigation_id = $1 LIMIT 10",
            INV_ID,
        )
        print(f"  Count: {len(obs)}")
        for o in obs:
            print(f"    [{o['status']}] {o['source_adapter']}: {o['method'][:60]} -> {o['target']}")

    await pool.close()
    print("\n=== Done ===")

asyncio.run(main())
