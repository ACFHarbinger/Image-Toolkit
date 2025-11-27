import os
import torch
import torch.nn as nn
import torch.optim as optim

from PIL import Image
from torchvision import transforms
from torchvision.utils import save_image
from torch.utils.data import Dataset, DataLoader
from tqdm import tqdm


class GanWrapper:
    # --- Cancellation Flag ---
    is_cancelled = False
    
    @staticmethod
    def cancel_process():
        GanWrapper.is_cancelled = True
        print("[CANCELLED] GAN process cancellation requested.")
        
    def __init__(self, model_name="bryandlee/animegan2-pytorch:main", device="cuda" if torch.cuda.is_available() else "cpu"):
        self.device = device
        GanWrapper.is_cancelled = False # Reset flag on new instance creation
        
        print(f"Initializing GAN Wrapper on {self.device}...")
        
        try:
            # We assume this is fast and does not need cancellation checks.
            self.netG = torch.hub.load(model_name, "generator", device=device, pretrained="face_paint_512_v2")
            self.netG.eval()
        except Exception as e:
            print(f"Error loading AnimeGAN: {e}")
            self.netG = None

        self.transform = transforms.Compose([
            transforms.Resize((512, 512)),
            transforms.ToTensor(),
            transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5)),
        ])

    def generate(self, input_image_path, output_path):
        if GanWrapper.is_cancelled:
            print("[CANCELLED] Generation aborted before start.")
            return

        if self.netG is None:
            raise RuntimeError("GAN Model not initialized.")
        if not os.path.exists(input_image_path):
            raise FileNotFoundError(f"Input image not found: {input_image_path}")

        image = Image.open(input_image_path).convert("RGB")
        image_tensor = self.transform(image).unsqueeze(0).to(self.device)

        with torch.no_grad():
            output = self.netG(image_tensor)
            
        if GanWrapper.is_cancelled:
            print("Generation stopped before save due to cancellation.")
            return

        output = (output + 1) / 2.0
        save_image(output, output_path)
        print(f"GAN Output saved to {output_path}")

    def train(self, style_data_dir, epochs=10, lr=1e-4, batch_size=1):
        if self.netG is None:
            return

        # --- Internal Dataset Class ---
        class SimpleFolderDataset(Dataset):
            def __init__(self, root_dir, transform):
                self.image_paths = []
                for root, _, files in os.walk(root_dir):
                    for file in files:
                        if file.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp')):
                            self.image_paths.append(os.path.join(root, file))
                self.transform = transform
            
            def __len__(self):
                return len(self.image_paths)
            
            def __getitem__(self, idx):
                try:
                    img = Image.open(self.image_paths[idx]).convert("RGB")
                    return self.transform(img)
                except Exception:
                    return torch.zeros((3, 512, 512))

        dataset = SimpleFolderDataset(style_data_dir, self.transform)
        if len(dataset) == 0:
            print("No images found.")
            return
            
        dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True, num_workers=0)

        self.netG.train()
        optimizer = optim.Adam(self.netG.parameters(), lr=lr)
        criterion = nn.L1Loss()

        for epoch in range(epochs):
            if GanWrapper.is_cancelled:
                print("Training stopped by cancellation.")
                return
                
            progress = tqdm(dataloader, desc=f"Epoch {epoch+1}/{epochs}")
            
            for batch_imgs in progress:
                if GanWrapper.is_cancelled:
                    progress.close()
                    print("Training stopped by cancellation.")
                    return
                    
                batch_imgs = batch_imgs.to(self.device)
                
                optimizer.zero_grad()
                output = self.netG(batch_imgs)
                loss = criterion(output, batch_imgs)
                loss.backward()
                optimizer.step()
                
                progress.set_postfix({"Loss": round(loss.item(), 4)})

        torch.save(self.netG.state_dict(), "custom_animegan.pt")
        print("GAN Training Finished. Saved to custom_animegan.pt")