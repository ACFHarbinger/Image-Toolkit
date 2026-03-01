use criterion::{black_box, criterion_group, criterion_main, Criterion, BenchmarkId};
use base::core::{
    file_system::{get_files_by_extension_core, delete_files_by_extensions_core},
    image_converter::convert_image_batch_core,
    image_merger::{merge_images_horizontal_core, merge_images_vertical_core, merge_images_grid_core},
};
use tempfile::tempdir;
use std::fs::File;
use image::{RgbImage, ImageBuffer};

/// Create a test RGB image
fn create_test_image(path: &str, width: u32, height: u32) {
    let img: RgbImage = ImageBuffer::from_fn(width, height, |x, y| {
        image::Rgb([((x + y) % 255) as u8, (x % 255) as u8, (y % 255) as u8])
    });
    img.save(path).unwrap();
}

/// Benchmark file system scanning
fn bench_file_scanning(c: &mut Criterion) {
    let mut group = c.benchmark_group("file_system");

    // Setup: Create directory with various file counts
    for count in [100, 1000].iter() {
        let dir = tempdir().unwrap();

        // Create files
        for i in 0..*count {
            let path = dir.path().join(format!("file_{}.txt", i));
            File::create(path).unwrap();
        }

        // Also create some non-matching files
        for i in 0..(*count / 10) {
            let path = dir.path().join(format!("other_{}.jpg", i));
            File::create(path).unwrap();
        }

        group.bench_with_input(
            BenchmarkId::new("scan_by_extension", count),
            count,
            |b, _| {
                b.iter(|| {
                    get_files_by_extension_core(
                        black_box(dir.path().to_str().unwrap()),
                        black_box("txt"),
                        black_box(false),
                    )
                });
            },
        );

        group.bench_with_input(
            BenchmarkId::new("scan_recursive", count),
            count,
            |b, _| {
                b.iter(|| {
                    get_files_by_extension_core(
                        black_box(dir.path().to_str().unwrap()),
                        black_box("txt"),
                        black_box(true),
                    )
                });
            },
        );
    }

    group.finish();
}

/// Benchmark image conversion (single and batch)
fn bench_image_conversion(c: &mut Criterion) {
    let mut group = c.benchmark_group("image_conversion");

    let dir = tempdir().unwrap();

    // Create test images of various sizes
    for (size_name, width, height) in [("small", 256, 256), ("medium", 512, 512), ("large", 1024, 1024)].iter() {
        let input_path = dir.path().join(format!("input_{}.jpg", size_name));
        let output_path = dir.path().join(format!("output_{}.png", size_name));

        create_test_image(input_path.to_str().unwrap(), *width, *height);

        group.bench_with_input(
            BenchmarkId::new("single_convert", size_name),
            size_name,
            |b, _| {
                b.iter(|| {
                    convert_image_batch_core(
                        black_box(&[(
                            input_path.to_str().unwrap().to_string(),
                            output_path.to_str().unwrap().to_string(),
                        )]),
                        black_box("png"),
                        black_box(false),
                        black_box(None),
                        black_box("crop"),
                    )
                });
            },
        );
    }

    // Batch conversion (100 small images)
    let mut batch_pairs = Vec::new();
    for i in 0..100 {
        let input_path = dir.path().join(format!("batch_in_{}.jpg", i));
        let output_path = dir.path().join(format!("batch_out_{}.png", i));
        create_test_image(input_path.to_str().unwrap(), 256, 256);
        batch_pairs.push((
            input_path.to_str().unwrap().to_string(),
            output_path.to_str().unwrap().to_string(),
        ));
    }

    group.bench_function("batch_convert_100", |b| {
        b.iter(|| {
            convert_image_batch_core(
                black_box(&batch_pairs),
                black_box("png"),
                black_box(false),
                black_box(None),
                black_box("crop"),
            )
        });
    });

    group.finish();
}

/// Benchmark image merge operations
fn bench_image_merge(c: &mut Criterion) {
    let mut group = c.benchmark_group("image_merge");

    let dir = tempdir().unwrap();

    // Create test images for merging
    for count in [4, 10, 25].iter() {
        let mut paths = Vec::new();
        for i in 0..*count {
            let path = dir.path().join(format!("merge_{}.jpg", i));
            create_test_image(path.to_str().unwrap(), 256, 256);
            paths.push(path.to_str().unwrap().to_string());
        }

        let output_path = dir.path().join("merged_output.jpg");

        group.bench_with_input(
            BenchmarkId::new("horizontal", count),
            count,
            |b, _| {
                b.iter(|| {
                    merge_images_horizontal_core(
                        black_box(&paths),
                        black_box(output_path.to_str().unwrap()),
                        black_box(0),
                        black_box("center"),
                    )
                });
            },
        );

        group.bench_with_input(
            BenchmarkId::new("vertical", count),
            count,
            |b, _| {
                b.iter(|| {
                    merge_images_vertical_core(
                        black_box(&paths),
                        black_box(output_path.to_str().unwrap()),
                        black_box(0),
                        black_box("center"),
                    )
                });
            },
        );

        group.bench_with_input(
            BenchmarkId::new("grid", count),
            count,
            |b, _| {
                let side = (*count as f64).sqrt().ceil() as u32;
                b.iter(|| {
                    merge_images_grid_core(
                        black_box(&paths),
                        black_box(output_path.to_str().unwrap()),
                        black_box(side),
                        black_box(side),
                        black_box(0),
                    )
                });
            },
        );
    }

    group.finish();
}

/// Benchmark file deletion
fn bench_file_deletion(c: &mut Criterion) {
    let mut group = c.benchmark_group("file_deletion");

    for count in [100, 1000].iter() {
        group.bench_with_input(
            BenchmarkId::new("delete_by_extension", count),
            count,
            |b, &count| {
                b.iter_batched(
                    || {
                        // Setup: Create temp dir with files
                        let dir = tempdir().unwrap();
                        for i in 0..count {
                            let path = dir.path().join(format!("del_{}.tmp", i));
                            File::create(path).unwrap();
                        }
                        dir
                    },
                    |dir| {
                        // Benchmark: Delete all .tmp files
                        delete_files_by_extensions_core(
                            black_box(dir.path().to_str().unwrap()),
                            black_box(&["tmp".to_string()]),
                        )
                    },
                    criterion::BatchSize::SmallInput,
                );
            },
        );
    }

    group.finish();
}

criterion_group!(
    benches,
    bench_file_scanning,
    bench_image_conversion,
    bench_image_merge,
    bench_file_deletion
);
criterion_main!(benches);
