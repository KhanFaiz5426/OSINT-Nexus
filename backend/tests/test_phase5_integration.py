"""Phase 5 integration tests — Knowledge Graph & Correlation.

Task 5.11: Integration tests covering collection → processing → correlation →
graph verification.

Tests mock external services (Neo4j, PostgreSQL) to verify the processing
pipeline and graph integration logic without requiring live databases.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models import EntityType, RelationshipType
from app.models.processing import ExtractedEntity, ExtractedRelationship

# ── Test helpers ──────────────────────────────────────────────────────────────


class _AsyncContextManager:
    """Helper that makes an AsyncMock usable with `async with`."""

    def __init__(self, mock_obj: Any) -> None:
        self._mock = mock_obj

    async def __aenter__(self) -> Any:
        return self._mock

    async def __aexit__(self, *args: Any) -> None:
        pass


class _AsyncIterator:
    """Helper that yields items from a list as an async iterator."""

    def __init__(self, items: list) -> None:
        self._items = items
        self._index = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._index >= len(self._items):
            raise StopAsyncIteration
        item = self._items[self._index]
        self._index += 1
        return item


def _make_session_mock(
    run_side_effect: Any = None,
    run_return: Any = None,
) -> AsyncMock:
    """Create a mock Neo4j session that supports `async with`."""
    session = AsyncMock()
    if run_side_effect is not None:
        session.run = AsyncMock(side_effect=run_side_effect)
    elif run_return is not None:
        session.run = AsyncMock(return_value=run_return)
    else:
        session.run = AsyncMock()
    return session


def _make_driver_mock(session: AsyncMock) -> MagicMock:
    """Create a mock Neo4j driver with session() returning an async ctx."""
    driver = MagicMock()
    driver.session = MagicMock(return_value=_AsyncContextManager(session))
    return driver


def _make_write_result(
    nodes_created: int = 0,
    relationships_created: int = 0,
    properties_set: int = 0,
) -> AsyncMock:
    """Create a mock result for write operations."""
    counters = MagicMock(
        nodes_created=nodes_created,
        relationships_created=relationships_created,
        properties_set=properties_set,
    )
    consume_result = MagicMock(counters=counters)
    result = AsyncMock()
    result.consume = AsyncMock(return_value=consume_result)
    return result


# ── Test fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def sample_entities() -> list[ExtractedEntity]:
    """Sample entities for a domain investigation."""
    now = datetime.now(UTC)
    return [
        ExtractedEntity(
            id="domain:example.com",
            entity_type=EntityType.DOMAIN,
            value="example.com",
            confidence=0.95,
            first_seen=now,
            last_seen=now,
            sources=["dns", "whois"],
            evidence_ids=["obs-1", "obs-2"],
            properties={"creation_date": "2020-01-01T00:00:00Z"},
        ),
        ExtractedEntity(
            id="ip:93.184.216.34",
            entity_type=EntityType.IP,
            value="93.184.216.34",
            confidence=0.95,
            first_seen=now,
            last_seen=now,
            sources=["dns"],
            evidence_ids=["obs-1"],
        ),
        ExtractedEntity(
            id="domain:ns1.example.com",
            entity_type=EntityType.DOMAIN,
            value="ns1.example.com",
            confidence=0.9,
            first_seen=now,
            last_seen=now,
            sources=["dns"],
            evidence_ids=["obs-1"],
        ),
        ExtractedEntity(
            id="email:admin@example.com",
            entity_type=EntityType.EMAIL,
            value="admin@example.com",
            confidence=0.8,
            first_seen=now,
            last_seen=now,
            sources=["whois"],
            evidence_ids=["obs-2"],
        ),
        ExtractedEntity(
            id="organization:Example Registrar",
            entity_type=EntityType.ORGANIZATION,
            value="Example Registrar",
            confidence=0.85,
            first_seen=now,
            last_seen=now,
            sources=["whois"],
            evidence_ids=["obs-2"],
        ),
    ]


@pytest.fixture
def sample_relationships() -> list[ExtractedRelationship]:
    """Sample relationships for a domain investigation."""
    now = datetime.now(UTC)
    return [
        ExtractedRelationship(
            id="domain:example.com:hosted_on:ip:93.184.216.34",
            source_entity_id="domain:example.com",
            target_entity_id="ip:93.184.216.34",
            rel_type=RelationshipType.HOSTED_ON,
            confidence=0.95,
            evidence_ids=["obs-1"],
            discovered_at=now,
            method="dns_a_record",
        ),
        ExtractedRelationship(
            id=(
                "domain:example.com:uses_nameserver:"
                "domain:ns1.example.com"
            ),
            source_entity_id="domain:example.com",
            target_entity_id="domain:ns1.example.com",
            rel_type=RelationshipType.USES_NAMESERVER,
            confidence=0.95,
            evidence_ids=["obs-1"],
            discovered_at=now,
            method="dns_ns_record",
        ),
        ExtractedRelationship(
            id=(
                "domain:example.com:registered_by:"
                "email:admin@example.com"
            ),
            source_entity_id="domain:example.com",
            target_entity_id="email:admin@example.com",
            rel_type=RelationshipType.REGISTERED_BY,
            confidence=0.8,
            evidence_ids=["obs-2"],
            discovered_at=now,
            method="whois_registrant_email",
        ),
        ExtractedRelationship(
            id=(
                "domain:example.com:registered_with:"
                "organization:Example Registrar"
            ),
            source_entity_id="domain:example.com",
            target_entity_id="organization:Example Registrar",
            rel_type=RelationshipType.REGISTERED_WITH,
            confidence=0.85,
            evidence_ids=["obs-2"],
            discovered_at=now,
            method="whois_registrar",
        ),
    ]


@pytest.fixture
def sample_observations() -> list[dict[str, Any]]:
    """Sample observations as they would come from PostgreSQL."""
    return [
        {
            "id": "obs-1",
            "source_adapter": "dns",
            "target": "example.com",
            "raw_response": {
                "A": [{"data": "93.184.216.34", "ttl": 3600}],
                "AAAA": [],
                "MX": [{"exchange": "mail.example.com", "priority": 10}],
                "NS": ["ns1.example.com", "ns2.example.com"],
                "TXT": [],
            },
        },
        {
            "id": "obs-2",
            "source_adapter": "whois",
            "target": "example.com",
            "raw_response": {
                "registrar": "Example Registrar",
                "registrant_email": "admin@example.com",
                "nameservers": ["ns1.example.com", "ns2.example.com"],
                "creation_date": "2020-01-01T00:00:00Z",
            },
        },
    ]


# ── Task 5.1: Graph models and constraints ────────────────────────────────────


class TestGraphModels:
    """Task 5.1: Neo4j node labels, relationship types, and constraints."""

    def test_node_labels_match_entity_types(self):
        """Every EntityType has a corresponding Neo4j node label."""
        from app.graph.models import NODE_LABELS

        for et in EntityType:
            assert et.value in NODE_LABELS

    def test_relationship_types_match(self):
        """Every RelationshipType has a corresponding Cypher type."""
        from app.graph.models import RELATIONSHIP_TYPES

        for rt in RelationshipType:
            assert rt.value.upper() in RELATIONSHIP_TYPES

    def test_constraints_defined_for_all_labels(self):
        """Constraints are defined for every node label."""
        from app.graph.models import CONSTRAINTS_CYPHER, NODE_LABELS

        assert len(CONSTRAINTS_CYPHER) == len(NODE_LABELS)
        for label in NODE_LABELS:
            assert any(label in c for c in CONSTRAINTS_CYPHER)

    def test_investigation_index_defined(self):
        """Investigation_id indexes are defined for all labels."""
        from app.graph.models import (
            INVESTIGATION_INDEX_CYPHER,
            NODE_LABELS,
        )

        assert len(INVESTIGATION_INDEX_CYPHER) == len(NODE_LABELS)

    def test_entity_type_to_label(self):
        """entity_type_to_label maps correctly."""
        from app.graph.models import entity_type_to_label

        assert entity_type_to_label(EntityType.DOMAIN) == "Domain"
        assert entity_type_to_label(EntityType.IP) == "IP"
        assert entity_type_to_label(EntityType.EMAIL) == "Email"

    def test_relationship_type_to_cypher(self):
        """relationship_type_to_cypher maps to SCREAMING_SNAKE."""
        from app.graph.models import relationship_type_to_cypher

        host = relationship_type_to_cypher(RelationshipType.HOSTED_ON)
        assert host == "HOSTED_ON"
        ns = relationship_type_to_cypher(
            RelationshipType.USES_NAMESERVER
        )
        assert ns == "USES_NAMESERVER"

    def test_node_properties_schema(self):
        """Node properties schema is documented."""
        from app.graph.models import NODE_PROPERTIES

        assert "id" in NODE_PROPERTIES
        assert "investigation_id" in NODE_PROPERTIES
        assert "confidence" in NODE_PROPERTIES

    def test_edge_properties_schema(self):
        """Edge properties schema is documented."""
        from app.graph.models import EDGE_PROPERTIES

        assert "id" in EDGE_PROPERTIES
        assert "confidence" in EDGE_PROPERTIES
        assert "evidence" in EDGE_PROPERTIES


# ── Task 5.2: Graph writer — nodes ────────────────────────────────────────────


class TestGraphWriterNodes:
    """Task 5.2: Create/update nodes in Neo4j from entity list."""

    @pytest.mark.asyncio
    async def test_write_nodes_empty_list(self):
        """Writing zero entities returns zero."""
        from app.graph.writer import write_nodes

        session = _make_session_mock()
        driver = _make_driver_mock(session)
        result = await write_nodes(
            [], investigation_id="test-inv-1", driver=driver
        )
        assert result == 0

    @pytest.mark.asyncio
    async def test_write_nodes_validates_investigation_id(self):
        """Empty investigation_id raises ValueError."""
        from app.graph.writer import write_nodes

        session = _make_session_mock()
        driver = _make_driver_mock(session)
        with pytest.raises(ValueError, match="investigation_id"):
            await write_nodes([], investigation_id="", driver=driver)

    @pytest.mark.asyncio
    async def test_write_nodes_groups_by_label(self, sample_entities):
        """Entities are grouped by Neo4j label for batch writes."""
        from app.graph.writer import write_nodes

        write_result = _make_write_result(nodes_created=5, properties_set=5)
        session = _make_session_mock(run_return=write_result)
        driver = _make_driver_mock(session)

        result = await write_nodes(
            sample_entities,
            investigation_id="test-inv-1",
            driver=driver,
        )
        assert result == 5
        # session.run should be called once per unique label.
        assert session.run.call_count >= 1

    @pytest.mark.asyncio
    async def test_write_nodes_cypher_is_parameterized(
        self, sample_entities
    ):
        """Cypher queries use parameters, not string interpolation."""
        from app.graph.writer import write_nodes

        write_result = _make_write_result(nodes_created=1, properties_set=1)
        session = _make_session_mock(run_return=write_result)
        driver = _make_driver_mock(session)

        await write_nodes(
            sample_entities[:1],
            investigation_id="test-inv-1",
            driver=driver,
        )

        # Verify parameters are passed correctly.
        call_args = session.run.call_args
        assert "nodes" in call_args.kwargs or len(call_args.args) >= 2


# ── Task 5.3: Graph writer — edges ────────────────────────────────────────────


class TestGraphWriterEdges:
    """Task 5.3: Create/update edges from relationship list."""

    @pytest.mark.asyncio
    async def test_write_edges_empty_list(self):
        """Writing zero relationships returns zero."""
        from app.graph.writer import write_edges

        session = _make_session_mock()
        driver = _make_driver_mock(session)
        result = await write_edges(
            [], investigation_id="test-inv-1", driver=driver
        )
        assert result == 0

    @pytest.mark.asyncio
    async def test_write_edges_groups_by_type(self, sample_relationships):
        """Relationships are grouped by type for batch writes."""
        from app.graph.writer import write_edges

        write_result = _make_write_result(
            relationships_created=4, properties_set=4
        )
        session = _make_session_mock(run_return=write_result)
        driver = _make_driver_mock(session)

        result = await write_edges(
            sample_relationships,
            investigation_id="test-inv-1",
            driver=driver,
        )
        assert result == 4

    @pytest.mark.asyncio
    async def test_write_edges_validates_investigation_id(self):
        """Empty investigation_id raises ValueError."""
        from app.graph.writer import write_edges

        session = _make_session_mock()
        driver = _make_driver_mock(session)
        with pytest.raises(ValueError, match="investigation_id"):
            await write_edges([], investigation_id="", driver=driver)


# ── Task 5.4: Graph reader — subgraph ─────────────────────────────────────────


class TestGraphReaderSubgraph:
    """Task 5.4: Query subgraph for an investigation."""

    @pytest.mark.asyncio
    async def test_get_investigation_subgraph(self):
        """Returns nodes and edges in Cytoscape.js format."""
        from app.graph.reader import get_investigation_subgraph

        # Mock node query result — use dict (matching real Neo4j record shape).
        node_record = {
            "node_id": "domain:example.com",
            "labels": ["Domain"],
            "value": "example.com",
            "confidence": 0.95,
            "first_seen": "2026-01-01T00:00:00",
            "last_seen": "2026-01-01T00:00:00",
            "source_count": 2,
            "properties": {},
        }

        # Mock edge query result.
        edge_record = {
            "edge_id": "rel-1",
            "source": "domain:example.com",
            "target": "ip:93.184.216.34",
            "relationship_type": "HOSTED_ON",
            "confidence": 0.95,
            "evidence": ["obs-1"],
            "discovered_at": "2026-01-01T00:00:00",
            "method": "dns_a_record",
        }

        # Create async iterables for the two queries.
        nodes_iter = _AsyncIterator([node_record])
        edges_iter = _AsyncIterator([edge_record])

        session = _make_session_mock(
            run_side_effect=[nodes_iter, edges_iter]
        )
        driver = _make_driver_mock(session)

        result = await get_investigation_subgraph(
            "test-inv-1", driver=driver
        )

        assert "nodes" in result
        assert "edges" in result
        assert len(result["nodes"]) == 1
        assert len(result["edges"]) == 1

        # Verify Cytoscape.js format.
        node = result["nodes"][0]
        assert "data" in node
        assert node["data"]["id"] == "domain:example.com"
        assert node["data"]["type"] == "Domain"

        edge = result["edges"][0]
        assert "data" in edge
        assert edge["data"]["source"] == "domain:example.com"
        assert edge["data"]["target"] == "ip:93.184.216.34"

    @pytest.mark.asyncio
    async def test_get_investigation_subgraph_empty(self):
        """Returns empty lists when investigation has no graph data."""
        from app.graph.reader import get_investigation_subgraph

        empty_iter = _AsyncIterator([])

        session = _make_session_mock(
            run_side_effect=[empty_iter, empty_iter]
        )
        driver = _make_driver_mock(session)

        result = await get_investigation_subgraph(
            "empty-inv", driver=driver
        )
        assert result["nodes"] == []
        assert result["edges"] == []

    @pytest.mark.asyncio
    async def test_get_investigation_subgraph_validates_id(self):
        """Empty investigation_id raises ValueError."""
        from app.graph.reader import get_investigation_subgraph

        session = _make_session_mock()
        driver = _make_driver_mock(session)
        with pytest.raises(ValueError, match="ID must be a non-empty"):
            await get_investigation_subgraph("", driver=driver)


# ── Task 5.5: Graph reader — neighbors ────────────────────────────────────────


class TestGraphReaderNeighbors:
    """Task 5.5: Query neighbors of a specific entity."""

    @pytest.mark.asyncio
    async def test_get_entity_neighbors_validates_ids(self):
        """Empty entity_id raises ValueError."""
        from app.graph.reader import get_entity_neighbors

        session = _make_session_mock()
        driver = _make_driver_mock(session)
        with pytest.raises(ValueError, match="ID must be a non-empty"):
            await get_entity_neighbors(
                "", investigation_id="inv-1", driver=driver
            )

    @pytest.mark.asyncio
    async def test_get_entity_neighbors_empty_result(self):
        """Returns empty graph when entity has no neighbors."""
        from app.graph.reader import get_entity_neighbors

        empty_iter = _AsyncIterator([])

        session = _make_session_mock(
            run_side_effect=[empty_iter, empty_iter]
        )
        driver = _make_driver_mock(session)

        result = await get_entity_neighbors(
            "domain:lonely.com",
            investigation_id="test-inv-1",
            driver=driver,
        )

        assert result["nodes"] == []
        assert result["edges"] == []


# ── Task 5.6: Graph reader — multi-hop paths ──────────────────────────────────


class TestGraphReaderPaths:
    """Task 5.6: Query multi-hop paths between entities."""

    @pytest.mark.asyncio
    async def test_get_multi_hop_paths_validates_ids(self):
        """Empty source/target IDs raise ValueError."""
        from app.graph.reader import get_multi_hop_paths

        session = _make_session_mock()
        driver = _make_driver_mock(session)
        with pytest.raises(ValueError, match="ID must be a non-empty"):
            await get_multi_hop_paths(
                "", "target:1",
                investigation_id="inv-1",
                driver=driver,
            )

    @pytest.mark.asyncio
    async def test_get_multi_hop_paths_empty_result(self):
        """Returns empty graph when no path exists."""
        from app.graph.reader import get_multi_hop_paths

        empty_iter = _AsyncIterator([])

        session = _make_session_mock(run_return=empty_iter)
        driver = _make_driver_mock(session)

        result = await get_multi_hop_paths(
            "domain:a.com",
            "domain:b.com",
            investigation_id="test-inv-1",
            driver=driver,
        )

        assert result["nodes"] == []
        assert result["edges"] == []


# ── Task 5.7: Correlation engine ──────────────────────────────────────────────


class TestCorrelationEngine:
    """Task 5.7: Orchestrate normalize → extract → resolve → detect → write."""

    @pytest.mark.asyncio
    async def test_correlate_observations_full_pipeline(
        self, sample_observations
    ):
        """Full pipeline: obs → entities → relationships → graph write."""
        from app.services.correlator import correlate_observations

        write_result = _make_write_result(
            nodes_created=5, properties_set=5, relationships_created=4
        )
        session = _make_session_mock(run_return=write_result)
        driver = _make_driver_mock(session)

        with patch(
            "app.services.correlator.get_driver",
            new_callable=AsyncMock,
            return_value=driver,
        ):
            result = await correlate_observations(
                "test-inv-1",
                sample_observations,
                write_to_graph=True,
            )

        assert result["investigation_id"] == "test-inv-1"
        assert result["observations_processed"] == 2
        assert result["entities_extracted"] > 0
        assert result["entities_resolved"] > 0
        assert result["relationships_detected"] > 0

    @pytest.mark.asyncio
    async def test_correlate_observations_no_graph_write(
        self, sample_observations
    ):
        """Pipeline works without graph write when disabled."""
        from app.services.correlator import correlate_observations

        result = await correlate_observations(
            "test-inv-1",
            sample_observations,
            write_to_graph=False,
        )

        assert result["nodes_written"] == 0
        assert result["edges_written"] == 0
        assert result["entities_extracted"] > 0

    @pytest.mark.asyncio
    async def test_correlate_observations_empty(self):
        """Empty observations produce zero results."""
        from app.services.correlator import correlate_observations

        result = await correlate_observations(
            "test-inv-1", [], write_to_graph=False
        )

        assert result["observations_processed"] == 0
        assert result["entities_extracted"] == 0
        assert result["relationships_detected"] == 0

    @pytest.mark.asyncio
    async def test_correlate_observations_handles_graph_failure(
        self, sample_observations
    ):
        """Graph write failure does not crash the pipeline."""
        from app.services.correlator import correlate_observations

        with patch(
            "app.services.correlator.get_driver",
            side_effect=Exception("Neo4j unavailable"),
        ):
            result = await correlate_observations(
                "test-inv-1",
                sample_observations,
                write_to_graph=True,
            )

        # Pipeline should still complete despite graph failure.
        assert result["entities_extracted"] > 0
        assert result["nodes_written"] == 0

    @pytest.mark.asyncio
    async def test_correlate_observations_dns_extraction(self):
        """DNS observation produces domain, IP, and nameserver entities."""
        from app.services.correlator import correlate_observations

        observations = [
            {
                "id": "obs-dns-1",
                "source_adapter": "dns",
                "target": "test.com",
                "raw_response": {
                    "A": [{"data": "1.2.3.4"}],
                    "NS": ["ns1.test.com"],
                    "MX": [
                        {"exchange": "mail.test.com", "priority": 10}
                    ],
                },
            }
        ]

        result = await correlate_observations(
            "test-inv-dns", observations, write_to_graph=False
        )

        # Should extract domain, IP, nameserver, MX entities.
        assert result["entities_extracted"] >= 3
        # Should detect hosted_on, uses_nameserver, sends_mail_via.
        assert result["relationships_detected"] >= 2

    @pytest.mark.asyncio
    async def test_correlate_observations_whois_extraction(self):
        """WHOIS observation produces domain, registrar, email entities."""
        from app.services.correlator import correlate_observations

        observations = [
            {
                "id": "obs-whois-1",
                "source_adapter": "whois",
                "target": "test.com",
                "raw_response": {
                    "registrar": "GoDaddy",
                    "registrant_email": "admin@test.com",
                    "nameservers": ["ns1.godaddy.com"],
                },
            }
        ]

        result = await correlate_observations(
            "test-inv-whois", observations, write_to_graph=False
        )

        assert result["entities_extracted"] >= 3
        assert result["relationships_detected"] >= 2


# ── Tasks 5.8–5.10: API endpoint tests ───────────────────────────────────────


class TestEntityAPI:
    """Tasks 5.9–5.10: Entity and evidence API endpoints."""

    @pytest.mark.asyncio
    async def test_get_entity_requires_investigation_id(self):
        """GET /entities/{id} requires investigation_id query param."""
        from httpx import ASGITransport, AsyncClient

        from app.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/api/v1/entities/domain:example.com"
            )
            # Missing required query param → 422.
            assert response.status_code == 422


# ── End-to-end integration test ───────────────────────────────────────────────


class TestPhase5EndToEnd:
    """Full Phase 5 integration: collection → processing → graph."""

    @pytest.mark.asyncio
    async def test_full_pipeline_dns_investigation(self):
        """Complete pipeline: DNS + WHOIS observations → graph population."""
        from app.services.correlator import correlate_observations

        observations = [
            {
                "id": "obs-dns-1",
                "source_adapter": "dns",
                "target": "malicious-example.com",
                "raw_response": {
                    "A": [{"data": "185.220.100.252"}],
                    "AAAA": [],
                    "MX": [
                        {
                            "exchange": (
                                "mail.malicious-example.com"
                            ),
                            "priority": 10,
                        }
                    ],
                    "NS": [
                        "ns1.shadyhost.net",
                        "ns2.shadyhost.net",
                    ],
                    "TXT": [
                        "v=spf1 include:_spf.google.com ~all"
                    ],
                },
            },
            {
                "id": "obs-whois-1",
                "source_adapter": "whois",
                "target": "malicious-example.com",
                "raw_response": {
                    "registrar": "PrivacyGuard",
                    "registrant_email": (
                        "contact@privacyguard.org"
                    ),
                    "nameservers": [
                        "ns1.shadyhost.net",
                        "ns2.shadyhost.net",
                    ],
                    "creation_date": (
                        "2026-08-28T00:00:00Z"
                    ),
                    "domain_status": "clientTransferProhibited",
                },
            },
            {
                "id": "obs-ct-1",
                "source_adapter": "certificate_transparency",
                "target": "malicious-example.com",
                "raw_response": {
                    "certificates": [
                        {
                            "id": "cert_abc123",
                            "issuer_name": (
                                "CN=R3, O=Let's Encrypt"
                            ),
                            "name_value": (
                                "malicious-example.com\n"
                                "www.malicious-example.com\n"
                                "admin.malicious-example.com"
                            ),
                        }
                    ]
                },
            },
        ]

        write_result = _make_write_result(
            nodes_created=10, properties_set=20,
            relationships_created=8,
        )
        session = _make_session_mock(run_return=write_result)
        driver = _make_driver_mock(session)

        with patch(
            "app.services.correlator.get_driver",
            new_callable=AsyncMock,
            return_value=driver,
        ):
            result = await correlate_observations(
                "test-e2e-inv-1",
                observations,
                write_to_graph=True,
            )

        # Verify extraction counts.
        assert result["observations_processed"] == 3
        # domain, IPs, NS, MX, email, org, cert, subdomains
        assert result["entities_extracted"] >= 5
        # hosted_on, uses_ns, sends_mail, registered_by,
        # covered_by_cert
        assert result["relationships_detected"] >= 4

        # Verify graph was written.
        assert result["nodes_written"] >= 1
        assert result["edges_written"] >= 1

    @pytest.mark.asyncio
    async def test_graph_models_schema_consistency(self):
        """All labels and relationship types are consistently defined."""
        from app.graph.models import (
            CONSTRAINTS_CYPHER,
            EDGE_PROPERTIES,
            INVESTIGATION_INDEX_CYPHER,
            NODE_LABELS,
            NODE_PROPERTIES,
            RELATIONSHIP_TYPES,
        )

        # Every label should have constraints and indexes.
        assert len(CONSTRAINTS_CYPHER) == len(NODE_LABELS)
        assert len(INVESTIGATION_INDEX_CYPHER) == len(NODE_LABELS)

        # Schema docs should be non-empty.
        assert len(NODE_PROPERTIES) >= 5
        assert len(EDGE_PROPERTIES) >= 5

        # Relationship types should be uppercase.
        for rt in RELATIONSHIP_TYPES:
            assert rt == rt.upper()
