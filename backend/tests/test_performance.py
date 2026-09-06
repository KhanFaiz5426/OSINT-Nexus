"""Performance tests — baseline benchmarks for core processing pipeline.

Task 9.7: Benchmarks for classification, normalization, extraction,
resolution, and confidence scoring with realistic data volumes.
"""

from __future__ import annotations

import statistics
import time
from datetime import UTC, datetime

from app.models import EntityType
from app.models.processing import ExtractedEntity


def _bench(func, *args, iterations: int = 1000, **kwargs) -> dict:
    """Run a function multiple times and return timing stats."""
    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        times.append(elapsed)
    return {
        "iterations": iterations,
        "total_ms": round(statistics.mean(times) * 1000, 3),
        "mean_us": round(statistics.mean(times) * 1_000_000, 1),
        "median_us": round(statistics.median(times) * 1_000_000, 1),
        "p95_us": round(sorted(times)[int(len(times) * 0.95)] * 1_000_000, 1),
        "stdev_us": round(statistics.stdev(times) * 1_000_000, 1) if len(times) > 1 else 0,
    }


# ── Benchmarks ───────────────────────────────────────────────────────────────


def test_bench_classifier():
    from app.services.classifier import classify_target

    targets = [
        "example.com", "93.184.216.34", "admin@example.com",
        "https://example.com/path", "cyberresearcher42",
        "sub.domain.co.uk", "192.168.1.1", "user+tag@gmail.com",
    ]

    results = {}
    for target in targets:
        stats = _bench(classify_target, target, iterations=5000)
        results[f"classify({target[:20]})"] = stats["mean_us"]

    # Overall benchmark
    all_stats = _bench(classify_target, "example.com", iterations=10000)
    results["overall"] = all_stats

    assert all_stats["mean_us"] < 50, f"Classification too slow: {all_stats['mean_us']}us"
    return results


def test_bench_normalizer():
    from app.services.normalizer import normalize_domain, normalize_email, normalize_ip

    results = {}
    results["normalize_domain"] = _bench(normalize_domain, "EXAMPLE.COM.", iterations=5000)
    results["normalize_ip"] = _bench(normalize_ip, "192.168.001.001", iterations=5000)
    results["normalize_email"] = _bench(normalize_email, "Admin@Example.Com", iterations=5000)

    for name, stats in results.items():
        assert stats["mean_us"] < 50, f"{name} too slow: {stats['mean_us']}us"

    return {k: v["mean_us"] for k, v in results.items()}


def test_bench_extractor_dns():
    from app.services.extractor import extract_from_dns

    raw_response = {
        "A": [{"data": "93.184.216.34", "ttl": 3600}],
        "AAAA": [{"data": "2606:2800:220:1:248:1893:25c8:1946", "ttl": 3600}],
        "MX": [{"data": "mail.example.com", "priority": 10}],
        "NS": [{"data": f"ns{i}.example.com"} for i in range(4)],
        "TXT": [{"data": "v=spf1 include:_spf.example.com ~all"}],
    }

    stats = _bench(extract_from_dns, "example.com", raw_response, iterations=1000)
    assert stats["mean_us"] < 1000, f"DNS extraction too slow: {stats['mean_us']}us"
    return stats


def test_bench_confidence():
    from app.services.confidence import score_entity

    entity = ExtractedEntity(
        id="domain:example.com",
        entity_type=EntityType.DOMAIN,
        value="example.com",
        confidence=0.9,
        first_seen=datetime.now(UTC),
        last_seen=datetime.now(UTC),
        sources=["dns", "whois"],
        evidence_ids=["obs-001", "obs-002"],
    )

    stats = _bench(score_entity, entity, iterations=5000)
    assert stats["mean_us"] < 100, f"Confidence scoring too slow: {stats['mean_us']}us"
    return stats


def test_bench_resolver():
    from app.services.resolver import resolve_entities

    entities = [
        ExtractedEntity(
            id=f"domain:example{i}.com",
            entity_type=EntityType.DOMAIN,
            value=f"example{i}.com",
            confidence=0.9,
            sources=["dns"],
        )
        for i in range(50)
    ]
    # Add duplicates
    entities.extend([
        ExtractedEntity(
            id=f"domain:example{i}.com",
            entity_type=EntityType.DOMAIN,
            value=f"example{i}.com",
            confidence=0.8,
            sources=["whois"],
        )
        for i in range(25)
    ])

    stats = _bench(resolve_entities, entities, iterations=100)
    assert stats["mean_us"] < 5000, f"Resolver too slow: {stats['mean_us']}us"
    return stats


def test_bench_batch_classification():
    from app.services.classifier import classify_target

    targets = [
        "example.com", "93.184.216.34", "admin@example.com",
        "https://example.com/path", "test_user",
    ] * 20  # 100 targets

    stats = _bench(lambda: [classify_target(t) for t in targets], iterations=100)
    assert stats["mean_us"] < 5000, f"Batch classification too slow: {stats['mean_us']}us"
    return stats


def test_bench_full_pipeline():
    """Benchmark a simplified full pipeline: classify -> normalize -> extract."""
    from app.services.classifier import classify_target
    from app.services.extractor import extract_from_dns
    from app.services.normalizer import normalize_domain

    target = "example.com"
    raw_dns = {
        "A": [{"data": "93.184.216.34", "ttl": 3600}],
        "MX": [{"data": "mail.example.com", "priority": 10}],
        "NS": [{"data": "ns1.example.com"}],
    }

    def pipeline():
        classify_target(target)
        normalized = normalize_domain(target)
        entities, rels = extract_from_dns(normalized, raw_dns)
        return entities, rels

    stats = _bench(pipeline, iterations=1000)
    assert stats["mean_us"] < 300, f"Full pipeline too slow: {stats['mean_us']}us"
    return stats


# ── Runner ───────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    import json

    benchmarks = {}
    tests = [
        ("classifier", test_bench_classifier),
        ("normalizer", test_bench_normalizer),
        ("extractor_dns", test_bench_extractor_dns),
        ("confidence", test_bench_confidence),
        ("resolver", test_bench_resolver),
        ("batch_classification", test_bench_batch_classification),
        ("full_pipeline", test_bench_full_pipeline),
    ]

    print("=" * 60)
    print("OSINT Nexus — Performance Benchmarks")
    print("=" * 60)

    for name, test_fn in tests:
        try:
            result = test_fn()
            benchmarks[name] = result
            if isinstance(result, dict) and "mean_us" in result:
                mean = result['mean_us']
                p95 = result['p95_us']
                print(f"  {name:30s} {mean:>10.1f} us/op  (p95: {p95:.1f} us)")
            else:
                print(f"  {name:30s} {json.dumps(result, indent=2)[:80]}")
        except Exception as e:
            print(f"  {name:30s} FAILED: {e}")
            benchmarks[name] = {"error": str(e)}

    print("=" * 60)
    print("All benchmarks completed.")

    # Save results
    output_path = "benchmark_results.json"
    with open(output_path, "w") as f:
        json.dump(benchmarks, f, indent=2, default=str)
    print(f"Results saved to {output_path}")
