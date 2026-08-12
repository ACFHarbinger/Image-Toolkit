#include <iostream>

#include "single_module_template/greet.hpp"

int main(int argc, char** argv) {
    std::string name = argc > 1 ? argv[1] : "world";
    std::cout << single_module_template::greet(name) << std::endl;
    return 0;
}
