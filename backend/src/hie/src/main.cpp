#include <iostream>

#include "greet.hpp"

int main(int argc, char** argv) {
    std::string name = argc > 1 ? argv[1] : "world";
    std::cout << hybrid_image_editor::greet(name) << std::endl;
    return 0;
}
