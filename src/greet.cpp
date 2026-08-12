#include "single_module_template/greet.hpp"

namespace single_module_template {

std::string greet(const std::string& name) {
    return "Hello, " + name + "!";
}

}  // namespace single_module_template
