"""Pure-logic tests for Cloud Compute usage-row aggregation (#490)."""

from backend.src.web.cloud.compute.usage import (
    UsageRow,
    aggregate_usage_rows,
    format_bytes,
    format_duration,
    format_usd,
    parse_bytes,
    parse_duration_seconds,
)


def test_parse_duration_and_bytes():
    assert parse_duration_seconds(14.2) == 14.2
    assert parse_duration_seconds("14.2s") == 14.2
    assert parse_duration_seconds("1m 30s") == 90
    assert parse_duration_seconds("In Flight") == 0
    assert parse_bytes("28.5 MB") == 28_500_000
    assert parse_bytes(1024) == 1024
    assert parse_bytes("~12.4 MB") == 12_400_000


def test_from_worker_usage_json():
    row = UsageRow.from_mapping(
        {
            "job_id": "job-1",
            "provider": "gcd",
            "task": "extract_gif",
            "status": "success",
            "duration_seconds": 4.2,
            "peak_rss_kib": 80_000,
            "output_uris": ["gs://res/clip.gif"],
        }
    )
    assert row.provider == "gcd"
    assert row.duration_seconds == 4.2
    assert row.peak_rss_kib == 80_000
    assert row.cost_usd > 0
    assert row.status == "success"


def test_from_ui_placeholder_dict():
    row = UsageRow.from_mapping(
        {
            "timestamp": "2026-08-31 19:00:00",
            "job_id": "job-12345",
            "provider": "GCD",
            "task": "Frame Extraction",
            "duration": "In Flight",
            "egress": "~12.4 MB",
            "cost": "< $0.01",
        }
    )
    assert row.provider == "gcd"
    assert row.status == "in_flight"
    assert row.duration_seconds == 0
    assert row.egress_bytes == 12_400_000


def test_aggregate_empty():
    summary = aggregate_usage_rows([])
    assert summary.total_jobs == 0
    assert summary.success_rate == 1.0
    assert summary.success_rate_label == "100%"
    assert summary.cost_label == "$0.00"


def test_aggregate_mixed_and_provider_split():
    rows = [
        UsageRow.from_mapping(
            {
                "job_id": "a",
                "provider": "gcd",
                "status": "success",
                "duration_seconds": 10,
                "egress_bytes": 1_000_000,
            }
        ),
        UsageRow.from_mapping(
            {
                "job_id": "b",
                "provider": "gcd",
                "status": "error",
                "duration_seconds": 2,
            }
        ),
        UsageRow.from_mapping(
            {
                "job_id": "c",
                "provider": "cloudflare",
                "duration": "In Flight",
            }
        ),
    ]
    summary = aggregate_usage_rows(rows)
    assert summary.total_jobs == 3
    assert summary.successes == 1
    assert summary.failures == 1
    assert summary.in_flight == 1
    assert summary.success_rate == 0.5
    assert summary.total_duration_seconds == 12
    assert "gcd" in summary.by_provider
    assert summary.by_provider["gcd"].jobs == 2
    assert summary.by_provider["cloudflare"].jobs == 1


def test_formatters():
    assert format_duration(0) == "0s"
    assert format_duration(90) == "1m 30s"
    assert format_bytes(0) == "0 B"
    assert "MB" in format_bytes(2_500_000)
    assert format_usd(0) == "$0.00"
    assert format_usd(0.0012).startswith("$0.00")
