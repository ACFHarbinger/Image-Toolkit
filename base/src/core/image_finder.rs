use image::ImageReader;
#[cfg(feature = "python")]
use pyo3::prelude::*;
use rayon::prelude::*;
use sha2::{Digest, Sha256};
use std::collections::HashMap;
use std::fs::File;
use std::io::Read;
use walkdir::WalkDir;

// --- Helper Functions ---

fn compute_sha256(path: &str) -> Option<String> {
    let mut file = match File::open(path) {
        Ok(f) => f,
        Err(_) => return None,
    };
    let mut hasher = Sha256::new();
    let mut buffer = [0; 65536]; // 64KB chunk

    loop {
        match file.read(&mut buffer) {
            Ok(0) => break,
            Ok(n) => hasher.update(&buffer[..n]),
            Err(_) => return None,
        }
    }

    Some(hex::encode(hasher.finalize()))
}

fn compute_phash(path: &str) -> Option<(String, u64)> {
    // 1. Open
    let img = match ImageReader::open(path) {
        Ok(reader) => match reader.decode() {
            Ok(i) => i,
            Err(_) => return None,
        },
        Err(_) => return None,
    };

    // 2. Resize to 8x8 and Grayscale
    // resize_exact gives exactly 8x8. FilterType::Triangle (Bilinear) is fast and good enough.
    let small = img
        .resize_exact(8, 8, image::imageops::FilterType::Triangle)
        .to_luma8();

    // 3. Compute Mean
    let mut sum: u32 = 0;
    for p in small.pixels() {
        sum += p[0] as u32;
    }
    let mean = sum / 64;

    // 4. Compute Hash
    let mut hash: u64 = 0;
    for (i, p) in small.pixels().enumerate() {
        if p[0] as u32 > mean {
            hash |= 1 << i;
        }
    }

    Some((path.to_string(), hash))
}

fn hamming_distance(h1: u64, h2: u64) -> u32 {
    (h1 ^ h2).count_ones()
}

// --- PyFunctions ---

#[cfg(feature = "python")]
#[pyfunction]
pub fn find_duplicate_images(
    py: Python,
    directory: String,
    extensions: Vec<String>,
    recursive: bool,
) -> PyResult<HashMap<String, Vec<String>>> {
    let exts: Vec<String> = extensions
        .iter()
        .map(|e| e.trim_start_matches('.').to_lowercase())
        .collect();

    let duplicates: HashMap<String, Vec<String>> = py.detach(|| {
        let walker = if recursive {
            WalkDir::new(&directory).into_iter()
        } else {
            WalkDir::new(&directory).max_depth(1).into_iter()
        };

        let paths: Vec<String> = walker
            .filter_map(|e| e.ok())
            .filter(|e| e.file_type().is_file())
            .filter(|e| {
                e.path()
                    .extension()
                    .and_then(|s| s.to_str())
                    .map(|s| exts.contains(&s.to_lowercase()))
                    .unwrap_or(false)
            })
            .map(|e| e.path().to_string_lossy().to_string())
            .collect();

        let hashes: Vec<(String, String)> = paths
            .par_iter()
            .filter_map(|p| compute_sha256(p).map(|h| (h, p.clone())))
            .collect();

        let mut groups: HashMap<String, Vec<String>> = HashMap::new();
        for (hash, path) in hashes {
            groups.entry(hash).or_default().push(path);
        }

        groups.into_iter().filter(|(_, v)| v.len() > 1).collect()
    });

    Ok(duplicates)
}

#[cfg(feature = "python")]
#[pyfunction]
pub fn find_similar_images_phash(
    py: Python,
    directory: String,
    extensions: Vec<String>,
    threshold: u32,
) -> PyResult<HashMap<String, Vec<String>>> {
    let exts: Vec<String> = extensions
        .iter()
        .map(|e| e.trim_start_matches('.').to_lowercase())
        .collect();

    let groups: HashMap<String, Vec<String>> = py.detach(|| {
        let paths: Vec<String> = WalkDir::new(&directory)
            .into_iter()
            .filter_map(|e| e.ok())
            .filter(|e| e.file_type().is_file())
            .filter(|e| {
                e.path()
                    .extension()
                    .and_then(|s| s.to_str())
                    .map(|s| exts.contains(&s.to_lowercase()))
                    .unwrap_or(false)
            })
            .map(|e| e.path().to_string_lossy().to_string())
            .collect();

        let path_hashes: Vec<(String, u64)> =
            paths.par_iter().filter_map(|p| compute_phash(p)).collect();

        // Grouping
        let mut results = HashMap::new();
        let mut visited = vec![false; path_hashes.len()];
        let mut group_id = 0;

        for i in 0..path_hashes.len() {
            if visited[i] {
                continue;
            }

            let mut group = vec![path_hashes[i].0.clone()];
            visited[i] = true;
            let hash_a = path_hashes[i].1;

            for j in (i + 1)..path_hashes.len() {
                if visited[j] {
                    continue;
                }

                let hash_b = path_hashes[j].1;

                if hamming_distance(hash_a, hash_b) <= threshold {
                    group.push(path_hashes[j].0.clone());
                    visited[j] = true;
                }
            }

            if group.len() > 1 {
                results.insert(format!("group_{}", group_id), group);
                group_id += 1;
            }
        }

        results
    });

    Ok(groups)
}

#[cfg(all(test, feature = "python"))]
mod tests {
    use super::*;
    use image::{Rgb, RgbImage};
    use tempfile::tempdir;

    #[test]
    fn test_find_duplicates() {
        let dir = tempdir().unwrap();
        let p1 = dir.path().join("img1.png");
        let p2 = dir.path().join("img2.png");
        let p3 = dir.path().join("unique.png");

        fn create_test_image(path: &str, color: [u8; 3]) {
            let mut img = RgbImage::new(100, 100);
            for x in 0..100 {
                for y in 0..100 {
                    img.put_pixel(x, y, Rgb(color));
                }
            }
            img.save(path).unwrap();
        }

        // Same content
        create_test_image(p1.to_str().unwrap(), [255, 0, 0]);
        create_test_image(p2.to_str().unwrap(), [255, 0, 0]);
        // Different content
        create_test_image(p3.to_str().unwrap(), [0, 255, 0]);

        Python::initialize();
        Python::attach(|py| {
            let dups = find_duplicate_images(
                py,
                dir.path().to_str().unwrap().to_string(),
                vec!["png".to_string()],
                false,
            )
            .unwrap();
            assert_eq!(dups.len(), 1);
            let paths = dups.values().next().unwrap();
            assert_eq!(paths.len(), 2);
        });
    }

    #[test]
    fn test_find_similar() {
        let dir = tempdir().unwrap();
        let p1 = dir.path().join("base.png");
        let p2 = dir.path().join("similar.png");
        let p3 = dir.path().join("diff.png");

        // Helper to create split image
        fn create_split_image(path: &str, horizontal: bool) {
            let mut img = RgbImage::new(100, 100);
            for x in 0..100 {
                for y in 0..100 {
                    let is_white = if horizontal { y < 50 } else { x < 50 };
                    let color = if is_white { [255, 255, 255] } else { [0, 0, 0] };
                    img.put_pixel(x, y, Rgb(color));
                }
            }
            img.save(path).unwrap();
        }

        // p1: Vertical Split (Left White, Right Black)
        create_split_image(p1.to_str().unwrap(), false);

        // p2: Same as p1 but with a small modification (noise pixel)
        {
            let mut img = image::open(&p1).unwrap().to_rgb8();
            img.put_pixel(0, 0, Rgb([128, 128, 128])); // Change one pixel
            img.save(p2.to_str().unwrap()).unwrap();
        }

        // p3: Horizontal Split (Top White, Bottom Black) - Should be very different hash
        create_split_image(p3.to_str().unwrap(), true);

        Python::initialize();
        Python::attach(|py| {
            // Threshold of 5 bits. 64 bits total.
            let sims = find_similar_images_phash(
                py,
                dir.path().to_str().unwrap().to_string(),
                vec!["png".to_string()],
                5,
            )
            .unwrap();

            // Check we have a group with p1 and p2
            let mut found_pair = false;
            for group in sims.values() {
                if group.len() == 2 {
                    // Verify elements are p1 and p2 (checking filenames since order might vary)
                    let s1 = p1.file_name().unwrap().to_str().unwrap();
                    let s2 = p2.file_name().unwrap().to_str().unwrap();

                    let has_p1 = group.iter().any(|s| s.contains(s1));
                    let has_p2 = group.iter().any(|s| s.contains(s2));

                    if has_p1 && has_p2 {
                        found_pair = true;
                    }
                }
                // Verify p3 is NOT in this group (implicit if len==2 and we found p1,p2)
            }
            assert!(
                found_pair,
                "Did not find the expected pair of similar images (p1, p2)"
            );
        });
    }
}
