import os
from celery import shared_task
from backend.src.core import (
    FSETool, ImageFormatConverter, 
    ImageMerger, FileDeleter, 
    DuplicateFinder, SimilarityFinder,
    WallpaperManager
)
# Ensure you handle DB initialization for Search if strictly necessary, 
# though Search is often fast enough for a direct View.

@shared_task(bind=True)
def task_convert_images(self, config):
    """Adapted from ConversionWorker"""
    input_path = config.get("input_path")
    output_format = config.get("output_format", "png").lower()
    output_path = config.get("output_path")
    delete_original = config.get("delete_original", False)
    input_formats = config.get("input_formats", [])

    if not os.path.exists(input_path):
        return {"status": "error", "message": "Input path not found"}

    if os.path.isdir(input_path):
        results = ImageFormatConverter.convert_batch(
            input_dir=input_path,
            inputs_formats=input_formats,
            output_dir=output_path or input_path,
            output_format=output_format,
            delete=delete_original
        )
        return {"status": "success", "count": len(results)}
    else:
        # Single file logic
        output_name = output_path
        if output_path and os.path.isdir(output_path):
             output_name = os.path.join(output_path, os.path.splitext(os.path.basename(input_path))[0])
        
        result = ImageFormatConverter.convert_single_image(
            image_path=input_path,
            output_name=output_name,
            format=output_format,
            delete=delete_original
        )
        return {"status": "success", "count": 1 if result else 0}

@shared_task
def task_merge_images(config):
    """Adapted from MergeWorker"""
    try:
        # Pre-processing logic from MergeWorker.run()
        input_paths = config["input_paths"]
        # ... (Include the FSETool expansion logic here if input_paths contains dirs)
        
        ImageMerger.merge_images(
            image_paths=input_paths, # Assumes list of file paths
            output_path=config["output_path"],
            direction=config["direction"],
            grid_size=config["grid_size"],
            align_mode=config["align_mode"],
            spacing=config["spacing"]
        )
        return {"status": "success", "output": config["output_path"]}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@shared_task
def task_delete_files(config):
    """Adapted from DeletionWorker"""
    target = config["target_path"]
    mode = config["mode"]
    
    if mode == 'directory':
        success = FileDeleter.delete_path(target)
        return {"status": "success" if success else "error"}
    else:
        # Logic to expand extensions using FSETool
        # ...
        deleted_count = 0 
        # for file in files: FileDeleter.delete_path(file) ...
        return {"status": "success", "deleted": deleted_count}

@shared_task(bind=True)
def task_scan_duplicates(self, directory, extensions, method):
    """
    Adapted from DuplicateScanWorker.
    Note: The QEventLoop/QThreadPool logic is simplified here. 
    Celery is already async; we run the scan sequentially or spawn sub-tasks.
    """
    self.update_state(state='PROGRESS', meta={'status': 'Indexing images...'})
    
    if method == 'exact':
        results = DuplicateFinder.find_duplicate_images(directory, extensions, recursive=True)
    else:
        # For 'phash', 'orb', etc., we must call the heavy logic.
        # Since we are essentially inside a worker process, we can run the 
        # SimilarityFinder logic directly.
        # Note: If SimilarityFinder relies on Qt signals, it needs refactoring.
        # Assuming SimilarityFinder is pure Python/OpenCV:
        images = SimilarityFinder.get_images_list(directory, extensions)
        
        # ... Perform hashing/feature extraction loop here ...
        # ... Perform comparison logic (_compare_phash, etc) here ...
        results = {} # Placeholder for actual logic result

    return {"status": "success", "results": results}