import os
os.environ["PYTEST_CURRENT_TEST"] = "1"

import asyncio
import time
import uuid
import random
from app.db.client import get_pool
from app.graph.writer import write_nodes, write_edges
from app.graph.reader import get_entity_neighbors, get_multi_hop_paths
from app.models.processing import ExtractedEntity, ExtractedRelationship
from app.models import EntityType, RelationshipType

async def benchmark_graph():
    print("Initializing Database...")
    inv_id = f"bench-{uuid.uuid4().hex[:8]}"
    
    # clear db
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM relationships")
        await conn.execute("DELETE FROM entities")
        await conn.execute("DELETE FROM investigations")
    
    # 1. Generate 30k nodes
    print('Generating 10,000 nodes...', flush=True)
    nodes = []
    types = list(EntityType)
    for i in range(10000):
        nodes.append(ExtractedEntity(id=f'node:{i}', entity_type=random.choice(types), value=f'val_{i}', confidence=0.9))
    nodes.append(ExtractedEntity(id='node:cycleA', entity_type=EntityType.IP, value='1', confidence=0.9))
    nodes.append(ExtractedEntity(id='node:cycleB', entity_type=EntityType.IP, value='2', confidence=0.9))
    nodes.append(ExtractedEntity(id='node:cycleC', entity_type=EntityType.IP, value='3', confidence=0.9))
    
    # Generate edges
    print("Generating 30,000 edges...", flush=True)
    edges = []
    rel_types = list(RelationshipType)
    hubs = [f"node:{i}" for i in range(50)]
    for i in range(30000):
        if random.random() < 0.2:
            src = random.choice(hubs)
        else:
            src = f"node:{random.randint(0, 9999)}"
            
        target = f"node:{random.randint(0, 9999)}"
        edges.append(ExtractedRelationship(
            id=f"rel:{i}",
            source_entity_id=src,
            target_entity_id=target,
            rel_type=random.choice(rel_types),
            confidence=0.9
        ))
    
    # Create a guaranteed cycle
    edges.append(ExtractedRelationship(id="cycle-1", source_entity_id="node:cycleA", target_entity_id="node:cycleB", rel_type=RelationshipType.HOSTED_ON))
    edges.append(ExtractedRelationship(id="cycle-2", source_entity_id="node:cycleB", target_entity_id="node:cycleC", rel_type=RelationshipType.HOSTED_ON))
    edges.append(ExtractedRelationship(id="cycle-3", source_entity_id="node:cycleC", target_entity_id="node:cycleA", rel_type=RelationshipType.HOSTED_ON))
    
    print("Writing to SQLite (autocommit mode)...")
    start = time.time()
    await write_nodes(nodes, investigation_id=inv_id)
    await write_edges(edges, investigation_id=inv_id)
    print(f"Write completed in {time.time() - start:.2f}s")
    
    # 2. Benchmarks
    print("\n--- Running Benchmarks ---")
    
    # 1-hop
    start = time.time()
    for _ in range(50):
        await get_entity_neighbors(random.choice(hubs), investigation_id=inv_id, max_depth=1)
    dur = (time.time() - start) / 50 * 1000
    print(f"1-hop traversal (avg over 50): {dur:.2f}ms")
    
    # Bounded 4-hop
    start = time.time()
    for _ in range(10):
        await get_entity_neighbors(random.choice(hubs), investigation_id=inv_id, max_depth=4)
    dur = (time.time() - start) / 10 * 1000
    print(f"4-hop traversal from hub (avg over 10): {dur:.2f}ms")
    
    # Multi-hop paths (BFS)
    start = time.time()
    for _ in range(10):
        src = random.choice(hubs)
        tgt = random.choice(hubs)
        await get_multi_hop_paths(src, tgt, investigation_id=inv_id, max_hops=4)
    dur = (time.time() - start) / 10 * 1000
    print(f"4-hop shortest path search (avg over 10): {dur:.2f}ms")
    
    # Cyclic check
    start = time.time()
    res = await get_entity_neighbors('node:cycleA', investigation_id=inv_id, max_depth=10)
    dur = (time.time() - start) * 1000
    num_nodes = len(res['nodes'])
    print(f"Cyclic graph traversal (depth 10): {dur:.2f}ms. Returned {num_nodes} nodes.", flush=True)

if __name__ == "__main__":
    asyncio.run(benchmark_graph())
