#pragma once

#include <torch/script.h> // Required for torch::jit::script::Module
#include <torch/torch.h>  // Required for torch::Device
#include <string>
#include <vector>

/**
 * @class SiameseModelLoader
 * @brief Singleton class to load a TorchScript ResNet model and generate embeddings.
 * * This class manages the lifecycle of the PyTorch model, ensuring it is loaded
 * only once (Singleton pattern) and handles the inference pipeline.
 */
class SiameseModelLoader {
private:
    // The serialized TorchScript module
    torch::jit::script::Module module;
    
    // The device (CPU or CUDA) determined at runtime
    torch::Device device;
    
    // Flag to check if model loaded successfully
    bool is_loaded;

    // Private Constructor (Singleton)
    SiameseModelLoader();

    // Internal helper to load weights from the .pt file
    void loadModel();

public:
    // Delete copy constructor and assignment operator to ensure unique instance
    SiameseModelLoader(const SiameseModelLoader&) = delete;
    void operator=(const SiameseModelLoader&) = delete;

    /**
     * @brief Access the singleton instance of the loader.
     * @return Reference to the static SiameseModelLoader instance.
     */
    static SiameseModelLoader& getInstance();

    /**
     * @brief Generates a 512-dimensional embedding vector for a given image.
     * * @param img_path Absolute or relative path to the image file.
     * @return std::vector<float> A flat vector of size 512 containing the embedding. 
     * Returns an empty vector if inference fails.
     */
    std::vector<float> getEmbedding(const std::string& img_path);
};