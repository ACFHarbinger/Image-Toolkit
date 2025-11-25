cmake_minimum_required(VERSION 3.0 FATAL_ERROR)
project(Models)

# Find LibTorch
# Pass -DCMAKE_PREFIX_PATH=/path/to/libtorch when running cmake
find_package(Torch REQUIRED)

# Find OpenCV
find_package(OpenCV REQUIRED)

add_executable(Models SiameseModelLoader.cpp SiameseModelLoader.hpp)
target_link_libraries(Models "${TORCH_LIBRARIES}" "${OpenCV_LIBS}")

# C++14 or C++17 is usually required for LibTorch
set_property(TARGET Models PROPERTY CXX_STANDARD 14)