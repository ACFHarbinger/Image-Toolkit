"""Constants relocated from backend/src or gui/src modules under this subpackage (module-level ALL_CAPS assignments)."""

from typing import Dict
import math

# --- from backend/src/pipeline/stitch_trainer.py ---
DEFAULT_CONFIG: Dict = {'image_dir': '', 'val_split': 0.1, 'dataset_size': 50000, 'patch_hw': [256, 256], 'max_dx': 0.5, 'max_dy': 0.5, 'max_angle': math.pi / 6, 'max_log_s': 0.25, 'mpeg_noise_prob': 0.3, 'dimming_prob': 0.4, 'neg_pair_prob': 0.1, 'augment': True, 'enc_channels': 256, 'num_heads': 8, 'num_ca_layers': 2, 'pretrained': True, 'epochs': 30, 'batch_size': 32, 'num_workers': 4, 'lr': 0.0003, 'weight_decay': 0.0001, 'warmup_epochs': 2, 'grad_clip': 1.0, 'amp': True, 'lambda_param': 1.0, 'lambda_photo': 0.5, 'lambda_sym': 0.2, 'huber_delta': 0.1, 'warmup_steps': 500, 'output_dir': 'stitch_checkpoints', 'save_every': 5, 'log_every': 50, 'loftr_distill': False, 'distill_weight': 0.3}
