# SDXL/LoRA target-module lists.
#
# Previously redeclared identically (byte-for-byte, just reformatted) in four
# separate tuner files: dream_booth_tuner.py, lo_ra_tuner.py,
# lo_ra_tuner_config.py, lo_ra_tuner_v2.py.
SDXL_ATTN_TARGETS = (
    "to_q", "to_k", "to_v", "to_out.0",
    "proj_in", "proj_out",
    "ff.net.0.proj", "ff.net.2",
)
SDXL_CONV_TARGETS = (
    "conv1", "conv2", "conv_shortcut", "conv", "time_emb_proj",
)
TE_ATTN_TARGETS = ("q_proj", "k_proj", "v_proj", "out_proj")
