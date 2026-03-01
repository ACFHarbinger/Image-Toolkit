"""
Database performance benchmarks.

Measures PostgreSQL query performance, memory usage, and vector search operations.
"""

import sys
import numpy as np
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.image_database import PgvectorImageDatabase
from benchmark.utils import BenchmarkRunner, measure_memory


runner = BenchmarkRunner("Database Operations")


@runner.benchmark("insert_tags_100", iterations=3)
@measure_memory
def bench_insert_tags_100():
    """Insert 100 tags."""
    db = PgvectorImageDatabase(embed_dim=128)

    for i in range(100):
        db.add_tag(f"benchmark_tag_{i}", type="test")

    # Cleanup
    for i in range(100):
        db.delete_tag(f"benchmark_tag_{i}")

    db.conn.close()


@runner.benchmark("insert_tags_1000", iterations=3)
@measure_memory
def bench_insert_tags_1000():
    """Insert 1000 tags."""
    db = PgvectorImageDatabase(embed_dim=128)

    for i in range(1000):
        db.add_tag(f"benchmark_tag_{i}", type="test")

    # Cleanup
    for i in range(1000):
        db.delete_tag(f"benchmark_tag_{i}")

    db.conn.close()


@runner.benchmark("get_all_tags_fetchall", iterations=5)
@measure_memory
def bench_get_all_tags():
    """Retrieve all tags using fetchall()."""
    db = PgvectorImageDatabase(embed_dim=128)

    # Seed 500 tags
    for i in range(500):
        db.add_tag(f"bench_tag_{i}", type="test")

    # Benchmark retrieval
    tags = db.get_all_tags()

    # Cleanup
    for i in range(500):
        db.delete_tag(f"bench_tag_{i}")

    db.conn.close()
    return len(tags)


@runner.benchmark("insert_groups_100", iterations=3)
@measure_memory
def bench_insert_groups():
    """Insert 100 groups with 5 subgroups each."""
    db = PgvectorImageDatabase(embed_dim=128)

    for g in range(100):
        group_name = f"bench_group_{g}"
        db.add_group(group_name)

        for s in range(5):
            db.add_subgroup(f"bench_sub_{s}", group_name)

    # Cleanup
    for g in range(100):
        db.delete_group(f"bench_group_{g}")

    db.conn.close()


@runner.benchmark("bulk_image_insert_100", iterations=3)
@measure_memory
def bench_bulk_image_insert():
    """Insert 100 images with embeddings."""
    db = PgvectorImageDatabase(embed_dim=128)

    # Create test group
    db.add_group("benchmark_images")

    # Insert images with random embeddings
    for i in range(100):
        embedding = np.random.rand(128).astype(np.float32).tolist()
        db.add_image(
            path=f"/tmp/bench_img_{i}.jpg",
            embedding=embedding,
            group_name="benchmark_images",
            subgroup_name=None,
        )

    # Cleanup
    db.delete_group("benchmark_images")
    db.conn.close()


@runner.benchmark("vector_search_k10", iterations=10)
@measure_memory
def bench_vector_search_k10():
    """Similarity search returning 10 nearest neighbors."""
    db = PgvectorImageDatabase(embed_dim=128)

    # Seed 1000 images
    db.add_group("benchmark_search")
    for i in range(1000):
        embedding = np.random.rand(128).astype(np.float32).tolist()
        db.add_image(
            path=f"/tmp/search_img_{i}.jpg",
            embedding=embedding,
            group_name="benchmark_search",
        )

    # Benchmark search
    query_embedding = np.random.rand(128).astype(np.float32).tolist()
    results = db.search_similar_images(query_embedding, top_k=10)

    # Cleanup
    db.delete_group("benchmark_search")
    db.conn.close()

    return len(results)


@runner.benchmark("vector_search_k100", iterations=5)
@measure_memory
def bench_vector_search_k100():
    """Similarity search returning 100 nearest neighbors."""
    db = PgvectorImageDatabase(embed_dim=128)

    # Seed 1000 images
    db.add_group("benchmark_search")
    for i in range(1000):
        embedding = np.random.rand(128).astype(np.float32).tolist()
        db.add_image(
            path=f"/tmp/search_img_{i}.jpg",
            embedding=embedding,
            group_name="benchmark_search",
        )

    # Benchmark search
    query_embedding = np.random.rand(128).astype(np.float32).tolist()
    results = db.search_similar_images(query_embedding, top_k=100)

    # Cleanup
    db.delete_group("benchmark_search")
    db.conn.close()

    return len(results)


@runner.benchmark("image_tag_operations", iterations=5)
@measure_memory
def bench_image_tag_ops():
    """Add and retrieve tags for images."""
    db = PgvectorImageDatabase(embed_dim=128)

    db.add_group("bench_tag_ops")

    # Create 10 tags
    tags = [f"tag_{i}" for i in range(10)]
    for tag in tags:
        db.add_tag(tag)

    # Insert 50 images
    image_ids = []
    for i in range(50):
        embedding = np.random.rand(128).astype(np.float32).tolist()
        img_id = db.add_image(
            path=f"/tmp/tag_img_{i}.jpg",
            embedding=embedding,
            group_name="bench_tag_ops",
        )
        image_ids.append(img_id)

    # Add tags to each image
    for img_id in image_ids:
        for tag in tags[:5]:  # 5 tags per image
            db.add_tag_to_image(img_id, tag)

    # Retrieve tags (this is the N+1 query scenario)
    for img_id in image_ids:
        img_tags = db.get_image_tags(img_id)

    # Cleanup
    db.delete_group("bench_tag_ops")
    for tag in tags:
        db.delete_tag(tag)
    db.conn.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Database benchmarks")
    parser.add_argument("--save", action="store_true", help="Save results to JSON")
    parser.add_argument("--baseline", type=Path, help="Baseline file for regression check")
    args = parser.parse_args()

    runner.run()
    runner.print_results()

    if args.save:
        output_path = runner.save_json()
        print(f"Results saved to {output_path}")

    if args.baseline:
        passed = runner.check_regression(args.baseline)
        sys.exit(0 if passed else 1)
