#include <SiameseModelLoader.hpp>
#include <opencv2/opencv.hpp>
#include <iostream>
#include <memory>

class SiameseModelLoader {
private:
    torch::jit::script::Module module;
    torch::Device device;
    bool is_loaded;

    // Private constructor for Singleton pattern
    SiameseModelLoader() : device(torch::kCPU), is_loaded(false) {
        loadModel();
    }

    void loadModel() {
        try {
            // 1. Detect Device
            if (torch::cuda::is_available()) {
                device = torch::kCUDA;
                std::cout << "Device: CUDA" << std::endl;
            } else {
                device = torch::kCPU;
                std::cout << "Device: CPU" << std::endl;
            }

            // 2. Load the Traced Model (exported from Python)
            // Note: We cannot use torchvision.models directly in C++ without tracing first.
            module = torch::jit::load("resnet18_embedding.pt");
            module.to(device);
            module.eval(); // Set to inference mode
            is_loaded = true;
            
        } catch (const c10::Error& e) {
            std::cerr << "Error loading the model: " << e.msg() << std::endl;
            is_loaded = false;
        }
    }

public:
    // Delete copy constructor and assignment operator
    SiameseModelLoader(const SiameseModelLoader&) = delete;
    void operator=(const SiameseModelLoader&) = delete;

    // Thread-safe Singleton Instance (Meyers' Singleton)
    static SiameseModelLoader& getInstance() {
        static SiameseModelLoader instance;
        return instance;
    }

    std::vector<float> getEmbedding(const std::string& img_path) {
        if (!is_loaded) {
            std::cerr << "Model not loaded correctly." << std::endl;
            return {};
        }

        try {
            // --- Image Loading (OpenCV) ---
            cv::Mat img = cv::imread(img_path);
            if (img.empty()) {
                std::cerr << "Failed to load image: " << img_path << std::endl;
                return {};
            }

            // --- Preprocessing (Matching ResNet Default Transforms) ---
            
            // 1. Convert BGR (OpenCV default) to RGB
            cv::cvtColor(img, img, cv::COLOR_BGR2RGB);

            // 2. Resize and Center Crop
            // To keep C++ simple, we resize to 224x224 directly. 
            // For exact parity with Python's CenterCrop, you would resize to 256 first, then crop.
            cv::resize(img, img, cv::Size(224, 224));

            // 3. Convert to Tensor
            // Input is (H, W, C), needs to be converted to Float and Normalized [0, 1]
            torch::Tensor img_tensor = torch::from_blob(img.data, {1, 224, 224, 3}, torch::kByte);
            img_tensor = img_tensor.to(torch::kFloat32).div(255.0);

            // 4. Permute to (Batch, Channel, Height, Width) -> (1, 3, 224, 224)
            img_tensor = img_tensor.permute({0, 3, 1, 2});

            // 5. Normalize (ImageNet Mean and Std)
            // Mean: [0.485, 0.456, 0.406], Std: [0.229, 0.224, 0.225]
            img_tensor[0][0] = img_tensor[0][0].sub(0.485).div(0.229);
            img_tensor[0][1] = img_tensor[0][1].sub(0.456).div(0.224);
            img_tensor[0][2] = img_tensor[0][2].sub(0.406).div(0.225);

            img_tensor = img_tensor.to(device);

            // --- Inference ---
            torch::NoGradGuard no_grad; // Equivalent to with torch.no_grad():
            
            std::vector<torch::jit::IValue> inputs;
            inputs.push_back(img_tensor);

            at::Tensor output = module.forward(inputs).toTensor();

            // --- Post-processing ---
            // Move back to CPU and Flatten
            output = output.cpu().flatten();

            // Convert Tensor to std::vector<float>
            std::vector<float> embedding(output.data_ptr<float>(), output.data_ptr<float>() + output.numel());

            return embedding;

        } catch (const std::exception& e) {
            std::cerr << "Inference error: " << e.what() << std::endl;
            return {};
        }
    }
};

// Example Usage
int main() {
    // This call initializes the model (Singleton)
    auto& loader = SiameseModelLoader::getInstance();

    std::string imagePath = "test_image.jpg";
    std::vector<float> embedding = loader.getEmbedding(imagePath);

    if (!embedding.empty()) {
        std::cout << "Embedding generated successfully. Size: " << embedding.size() << std::endl;
        // Print first 5 values
        for(int i=0; i < 5; ++i) std::cout << embedding[i] << " ";
        std::cout << "..." << std::endl;
    }

    return 0;
}