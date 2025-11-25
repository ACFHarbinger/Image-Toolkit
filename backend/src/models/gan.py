import os
import torch
import torch.nn as nn
import torch.optim as optim
import torchvision.utils as vutils

from backend.src.models.subnets import Generator, Discriminator


class GAN:
    def __init__(self, z_dim=100, channels=3, n_filters=32, n_blocks=3, lr=0.0002, device=None):
        """
        Initializes the GAN, Optimizers, and Loss functions.
        """
        self.z_dim = z_dim
        self.device = device if device else torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
        print(f"Initializing GAN on {self.device}...")
        
        # Initialize Networks
        self.netG = Generator(z_dim, channels, n_filters, n_blocks).to(self.device)
        self.netD = Discriminator(channels, 1, n_filters, n_blocks).to(self.device)
        
        # Initialize Optimizers
        self.optimizerG = optim.Adam(self.netG.parameters(), lr=lr, betas=(0.5, 0.999))
        self.optimizerD = optim.Adam(self.netD.parameters(), lr=lr, betas=(0.5, 0.999))
        
        # Loss Function (BCEWithLogits combines Sigmoid + BCE for stability)
        self.criterion = nn.BCEWithLogitsLoss()

    def train(self, dataloader, epochs=50, save_path="./gan_checkpoints"):
        """
        Runs the training loop.
        """
        os.makedirs(save_path, exist_ok=True)
        self.netG.train()
        self.netD.train()

        print("Starting Training Loop...")
        
        for epoch in range(epochs):
            for i, (real_images, _) in enumerate(dataloader):
                batch_size = real_images.size(0)
                real_images = real_images.to(self.device)

                # ==========================
                # 1. Train Discriminator
                # ==========================
                self.netD.zero_grad()
                
                # A. Real Loss
                # Soft labels (0.9) sometimes help training stability, but 1.0 is standard
                label_real = torch.full((batch_size, 1), 1.0, device=self.device)
                output_real = self.netD(real_images)
                loss_real = self.criterion(output_real, label_real)
                
                # B. Fake Loss
                noise = torch.randn(batch_size, self.z_dim, device=self.device)
                fake_images = self.netG(noise)
                label_fake = torch.full((batch_size, 1), 0.0, device=self.device)
                
                # Detach() because we don't want to update G based on D's optimization
                output_fake = self.netD(fake_images.detach())
                loss_fake = self.criterion(output_fake, label_fake)
                
                # Update D
                loss_D = loss_real + loss_fake
                loss_D.backward()
                self.optimizerD.step()

                # ==========================
                # 2. Train Generator
                # ==========================
                self.netG.zero_grad()
                
                # We want D to think these are real (Label = 1)
                label_fool = torch.full((batch_size, 1), 1.0, device=self.device)
                output_generated = self.netD(fake_images) # Do NOT detach here
                
                # Update G
                loss_G = self.criterion(output_generated, label_fool)
                loss_G.backward()
                self.optimizerG.step()

                # Logging
                if i % 100 == 0:
                    print(f"[Epoch {epoch}/{epochs}][Batch {i}] Loss_D: {loss_D.item():.4f} Loss_G: {loss_G.item():.4f}")

            # End of Epoch Maintenance
            self.save_checkpoint(f"{save_path}/gan_epoch_{epoch}.pth")
            self.generate_and_save_images(epoch, save_path)

        print("Training Complete.")

    def generate_image(self, num_images=1):
        """
        Generates images from random noise. Returns a Tensor.
        """
        self.netG.eval() # Switch to eval mode
        with torch.no_grad():
            noise = torch.randn(num_images, self.z_dim, device=self.device)
            generated_imgs = self.netG(noise)
        self.netG.train() # Switch back to train mode
        
        # Denormalize from [-1, 1] to [0, 1] for viewing
        return (generated_imgs + 1) / 2.0

    def generate_and_save_images(self, epoch, save_path):
        """
        Helper to save a grid of images during training.
        """
        imgs = self.generate_image(num_images=16)
        vutils.save_image(imgs, f"{save_path}/epoch_{epoch}_sample.png", nrow=4)

    def save_checkpoint(self, filepath):
        torch.save({
            'netG': self.netG.state_dict(),
            'netD': self.netD.state_dict(),
            'optG': self.optimizerG.state_dict(),
            'optD': self.optimizerD.state_dict()
        }, filepath)

    def load_checkpoint(self, filepath):
        if not os.path.exists(filepath):
            print("Checkpoint not found.")
            return
        checkpoint = torch.load(filepath, map_location=self.device)
        self.netG.load_state_dict(checkpoint['netG'])
        self.netD.load_state_dict(checkpoint['netD'])
        self.optimizerG.load_state_dict(checkpoint['optG'])
        self.optimizerD.load_state_dict(checkpoint['optD'])
        print(f"Checkpoint loaded: {filepath}")

# ==========================================
# 4. Usage Example
# ==========================================
if __name__ == "__main__":
    from torch.utils.data import DataLoader, TensorDataset

    # 1. Setup Dummy Data (Replace with your actual DataLoader)
    # Note: 3 blocks upsampels 4x4 -> 32x32. Input must be 32x32.
    print("Creating dummy dataset...")
    dummy_data = torch.randn(100, 3, 32, 32) # [N, C, H, W]
    dataset = TensorDataset(dummy_data, torch.zeros(100)) # labels ignored
    dataloader = DataLoader(dataset, batch_size=10, shuffle=True)

    # 2. Initialize GAN Manager
    gan = GAN(
        z_dim=100, 
        channels=3, 
        n_filters=32, 
        n_blocks=3, # Results in 32x32 output
        lr=0.0002
    )

    # 3. Train
    gan.train(dataloader, epochs=2)

    # 4. Generate specific image after training
    print("Generating final image...")
    final_img = gan.generate_image(num_images=1)
    print(f"Generated Image Shape: {final_img.shape}")