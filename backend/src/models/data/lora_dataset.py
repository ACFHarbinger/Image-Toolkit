import os
from PIL import Image
from torch.utils.data import Dataset


class LoRADataset(Dataset):
    def __init__(
        self, root_dir, tokenizer, size=1024, trigger="my_char", pruned_tags=None
    ):
        self.root_dir = root_dir
        self.tokenizer = tokenizer
        self.size = size
        self.trigger = trigger
        self.pruned_tags = (
            [t.strip().lower() for t in pruned_tags.split(",")] if pruned_tags else []
        )

        self.image_paths = [
            os.path.join(root_dir, f)
            for f in os.listdir(root_dir)
            if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))
        ]

    def __getitem__(self, idx):
        img_path = self.image_paths[idx]
        image = Image.open(img_path).convert("RGB")

        # Load associated .txt file
        tag_path = os.path.splitext(img_path)[0] + ".txt"
        if os.path.exists(tag_path):
            with open(tag_path, "r") as f:
                tags = [t.strip() for t in f.read().split(",")]

            # Feature Binding: Filter out tags we want the trigger word to 'own'
            filtered_tags = [t for t in tags if t.lower() not in self.pruned_tags]
            caption = f"{self.trigger}, " + ", ".join(filtered_tags)
        else:
            caption = self.trigger

        # Process image and tokenize caption
        inputs = self.tokenizer(
            caption, padding="max_length", truncation=True, return_tensors="pt"
        )
        return {
            "pixel_values": self.process_image(image),
            "input_ids": inputs.input_ids[0],
        }
