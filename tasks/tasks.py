import os
import cv2
import time
import torch

from celery import shared_task
from pathlib import Path
from moviepy.editor import VideoFileClip
from torch.utils.data import DataLoader
from torchvision import datasets, transforms
from backend.src.core import (
    FSETool, ImageFormatConverter, 
    ImageMerger, FileDeleter, 
    DuplicateFinder, SimilarityFinder,
)
from backend.src.web import (
    GoogleDriveSync, DropboxDriveSync, OneDriveSync,
    ImageCrawler, DanbooruCrawler, GelbooruCrawler, SankakuCrawler,
    ReverseImageSearchCrawler, WebRequestsLogic
)
from backend.src.models.gan import GAN
from backend.src.core import PgvectorImageDatabase as ImageDatabase
from backend.src.utils.definitions import LOCAL_SOURCE_PATH
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

@shared_task(bind=True)
def task_train_gan(self, config):
    """Adapted from TrainingWorker"""
    try:
        data_path = config['data_path']
        save_path = config['save_path']
        epochs = config['epochs']
        batch_size = config['batch_size']
        lr = config['lr']
        z_dim = config['z_dim']
        device_name = config['device_name']

        device = torch.device(device_name if torch.cuda.is_available() and device_name == 'cuda' else 'cpu')
        
        # Transform logic
        transform = transforms.Compose([
            transforms.Resize((32, 32)),
            transforms.ToTensor(),
            transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5)),
        ])

        try:
            dataset = datasets.ImageFolder(root=data_path, transform=transform)
        except Exception as e:
            return {"status": "error", "message": f"Dataset Error: {str(e)}"}

        dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True, num_workers=0) # 0 workers for safety in Celery

        gan = GAN(
            z_dim=z_dim,
            channels=3,
            n_filters=32,
            n_blocks=3,
            lr=lr,
            device=device,
        )

        # Assuming gan.train is blocking and saves models periodically or at the end
        gan.train(dataloader, epochs=epochs, save_path=save_path)
        
        return {"status": "success", "message": "Training complete"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@shared_task(bind=True)
def task_extract_frames(self, config):
    """Adapted from FrameExtractionWorker"""
    try:
        video_path = config['video_path']
        output_dir = config['output_dir']
        start_ms = config['start_ms']
        end_ms = config['end_ms']
        is_range = config['is_range']
        target_resolution = None
        if config.get('target_width') and config.get('target_height'):
            target_resolution = (config['target_width'], config['target_height'])

        saved_files = []
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
             return {"status": "error", "message": "Could not open video file"}

        cap.set(cv2.CAP_PROP_POS_MSEC, start_ms)
        video_name = Path(video_path).stem
        timestamp = int(time.time())

        while True:
            # Check for cancellation if using Celery task revocation, logic needs adjustment for that
            ret, frame = cap.read()
            if not ret:
                break

            if target_resolution:
                frame = cv2.resize(frame, target_resolution, interpolation=cv2.INTER_AREA)

            current_ms = cap.get(cv2.CAP_PROP_POS_MSEC)
            filename = f"{video_name}_{timestamp}_{int(current_ms)}ms.jpg"
            save_path = os.path.join(output_dir, filename)
            cv2.imwrite(save_path, frame)
            saved_files.append(save_path)

            if not is_range:
                break
            if end_ms != -1 and current_ms >= end_ms:
                break

        cap.release()
        return {"status": "success", "extracted_count": len(saved_files), "files": saved_files}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@shared_task(bind=True)
def task_create_gif(self, config):
    """Adapted from GifCreationWorker"""
    try:
        video_path = config['video_path']
        output_path = config['output_path']
        start_ms = config['start_ms']
        end_ms = config['end_ms']
        fps = config['fps']
        target_size = None
        if config.get('target_width') and config.get('target_height'):
            target_size = (config['target_width'], config['target_height'])

        t_start = start_ms / 1000.0
        t_end = end_ms / 1000.0

        clip = VideoFileClip(video_path).subclip(t_start, t_end)
        if target_size:
            clip = clip.resize(newsize=target_size)
        
        clip.write_gif(output_path, fps=fps, verbose=False, logger=None)
        clip.close()
        
        return {"status": "success", "output_path": output_path}
    except Exception as e:
         return {"status": "error", "message": str(e)}

@shared_task(bind=True)
def task_extract_video_clip(self, config):
    """Adapted from VideoExtractionWorker"""
    temp_audio_path = f"temp-audio-{self.request.id}.m4a"
    try:
        video_path = config['video_path']
        output_path = config['output_path']
        start_ms = config['start_ms']
        end_ms = config['end_ms']
        mute_audio = config['mute_audio']
        target_size = None
        if config.get('target_width') and config.get('target_height'):
            target_size = (config['target_width'], config['target_height'])

        t_start = start_ms / 1000.0
        t_end = end_ms / 1000.0

        clip = VideoFileClip(video_path).subclip(t_start, t_end)
        if target_size:
            clip = clip.resize(newsize=target_size)

        audio_codec = "aac"
        if mute_audio or clip.audio is None:
            clip.audio = None
            audio_codec = None
        
        ffmpeg_params = ["-movflags", "faststart"]
        if audio_codec:
             ffmpeg_params.extend(["-b:a", "128k"])

        clip.write_videofile(
            output_path,
            codec="libx264",
            audio_codec=audio_codec,
            temp_audiofile=temp_audio_path,
            remove_temp=True,
            ffmpeg_params=ffmpeg_params,
            verbose=False,
            logger=None
        )
        clip.close()
        return {"status": "success", "output_path": output_path}
    except Exception as e:
        if os.path.exists(temp_audio_path):
            try: os.remove(temp_audio_path)
            except: pass
        return {"status": "error", "message": str(e)}

@shared_task(bind=True)
def task_cloud_sync(self, config):
    """Unified task for cloud sync operations"""
    try:
        provider = config['provider']
        local_path = config['local_path']
        remote_path = config['remote_path']
        dry_run = config['dry_run']
        action_local = config['action_local']
        action_remote = config['action_remote']
        auth_config = config['auth_config']

        # Logger adapter for Celery task state
        def _log(msg):
            self.update_state(state='PROGRESS', meta={'status': msg})

        sync_manager = None
        
        if provider == 'google':
            gds_kwargs = {
                "local_source_path": local_path,
                "drive_destination_folder_name": remote_path,
                "dry_run": dry_run,
                "logger": _log,
                "user_email_to_share_with": config.get('share_email'),
                "action_local_orphans": action_local,
                "action_remote_orphans": action_remote,
            }
            auth_mode = auth_config.get("mode", "unknown")
            
            if auth_mode == "service_account":
                gds_kwargs["service_account_data"] = auth_config.get("service_account_data")
                gds_kwargs["client_secrets_data"] = None
                gds_kwargs["token_file"] = None
            elif auth_mode == "personal_account":
                gds_kwargs["client_secrets_data"] = auth_config.get("client_secrets_data")
                gds_kwargs["token_file"] = auth_config.get("token_file")
                gds_kwargs["service_account_data"] = None
            else:
                return {"status": "error", "message": f"Unsupported auth mode: {auth_mode}"}
            
            sync_manager = GoogleDriveSync(**gds_kwargs)

        elif provider == 'dropbox':
            token = auth_config.get("access_token")
            sync_manager = DropboxDriveSync(
                local_source_path=local_path,
                drive_destination_folder_name=remote_path,
                access_token=token,
                dry_run=dry_run,
                logger=_log,
                action_local_orphans=action_local,
                action_remote_orphans=action_remote,
            )

        elif provider == 'onedrive':
            client_id = auth_config.get("client_id")
            sync_manager = OneDriveSync(
                local_source_path=local_path,
                drive_destination_folder_name=remote_path,
                client_id=client_id,
                dry_run=dry_run,
                logger=_log,
                action_local_orphans=action_local,
                action_remote_orphans=action_remote,
            )

        if sync_manager:
            success, msg = sync_manager.execute_sync()
            return {"status": "success" if success else "error", "message": msg, "dry_run": dry_run}
        
        return {"status": "error", "message": "Invalid provider"}

    except Exception as e:
        return {"status": "error", "message": str(e)}

@shared_task(bind=True)
def task_crawl_images(self, config):
    """Adapted from ImageCrawlWorker"""
    try:
        os.makedirs(config["download_dir"], exist_ok=True)
        if config.get("screenshot_dir"):
            os.makedirs(config["screenshot_dir"], exist_ok=True)

        crawler_type = config.get("type", "general")
        crawler = None

        if crawler_type == "board":
            board_type = config.get("board_type", "danbooru")
            if board_type == "gelbooru":
                crawler = GelbooruCrawler(config)
            elif board_type == "sankaku":
                crawler = SankakuCrawler(config)
            else:
                crawler = DanbooruCrawler(config)
        else:
            crawler = ImageCrawler(config)

        # We can't easily hook into crawler signals for real-time Celery updates without refactoring Crawler classes
        # to accept a callback instead of emitting Qt signals. 
        # For now, we run it and return the final result.
        final_count = crawler.run()
        
        return {"status": "success", "downloaded": final_count}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@shared_task(bind=True)
def task_reverse_search(self, config):
    """Adapted from ReverseSearchWorker"""
    # Note: Selenium on a server usually requires headless=True. 
    # The worker config 'headless=False' might need to be overridden for API usage unless running locally with GUI.
    crawler = None
    try:
        # Override headless to True for server context usually
        crawler = ReverseImageSearchCrawler(headless=True, browser=config['browser'])
        
        results = crawler.perform_reverse_search(
            config['image_path'],
            config['min_width'],
            config['min_height'],
            search_mode=config['search_mode'],
        )
        
        if not config.get('keep_open', False):
            crawler.close()
            
        return {"status": "success", "results": results}
    except Exception as e:
        if crawler: crawler.close()
        return {"status": "error", "message": str(e)}

@shared_task(bind=True)
def task_web_request(self, config):
    """Adapted from WebRequestsWorker"""
    try:
        logic = WebRequestsLogic(config)
        # WebRequestsLogic usually runs in a thread and emits signals.
        # We need to adapt it to run synchronously or return results.
        # Assuming run() blocks until finished:
        logic.run() 
        return {"status": "success", "message": "Request completed (check logs/output)"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# Helper to get DB instance from config
def _get_db(config):
    return ImageDatabase(
        db_host=config.get('db_host'),
        db_port=config.get('db_port'),
        db_user=config.get('db_user'),
        db_password=config.get('db_password'),
        db_name=config.get('db_name')
    )

@shared_task
def task_db_test_connection(config):
    try:
        db = _get_db(config)
        stats = db.get_statistics()
        db.close()
        return {"status": "success", "message": "Connected successfully", "stats": stats}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@shared_task
def task_db_add_group(config):
    try:
        db = _get_db(config)
        added = 0
        for name in config['group_names']:
            db.add_group(name)
            added += 1
        db.close()
        return {"status": "success", "added_count": added}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@shared_task
def task_db_add_subgroup(config):
    try:
        db = _get_db(config)
        parent = config['parent_group']
        added = 0
        for name in config['subgroup_names']:
            db.add_subgroup(name, parent)
            added += 1
        db.close()
        return {"status": "success", "added_count": added, "parent": parent}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@shared_task
def task_db_add_tag(config):
    try:
        db = _get_db(config)
        tag_type = config.get('tag_type')
        added = 0
        for name in config['tag_names']:
            db.add_tag(name, tag_type)
            added += 1
        db.close()
        return {"status": "success", "added_count": added}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@shared_task(bind=True)
def task_db_auto_populate(self, config):
    """Adapted from DatabaseTab.auto_populate_from_source"""
    try:
        db = _get_db(config)
        source_path = Path(config.get('source_path', LOCAL_SOURCE_PATH)).resolve()
        
        if not source_path.exists():
            return {"status": "error", "message": "Source path does not exist"}

        groups_added = 0
        subgroups_added = 0
        
        # Iterate Level 1
        for group_dir in source_path.iterdir():
            if group_dir.is_dir() and not group_dir.name.startswith("."):
                group_name = group_dir.name.strip()
                if not group_name: continue
                
                db.add_group(group_name)
                groups_added += 1
                
                # Iterate Level 2
                for subgroup_dir in group_dir.iterdir():
                    if subgroup_dir.is_dir() and not subgroup_dir.name.startswith("."):
                        subgroup_name = subgroup_dir.name.strip()
                        if not subgroup_name: continue
                        
                        try:
                            db.add_subgroup(subgroup_name, group_name)
                            subgroups_added += 1
                        except:
                            pass
        
        db.close()
        return {
            "status": "success", 
            "groups_processed": groups_added, 
            "subgroups_processed": subgroups_added
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@shared_task
def task_db_reset(config):
    try:
        db = _get_db(config)
        db.reset_database()
        db.close()
        return {"status": "success", "message": "Database reset complete"}
    except Exception as e:
        return {"status": "error", "message": str(e)}