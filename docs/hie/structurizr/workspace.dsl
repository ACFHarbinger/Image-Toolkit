/*
 * Hybrid-Image-Editor (HIE) — Structurizr DSL workspace (C4 model)
 *
 * See docs/structurizr/README.md for rendering instructions.
 */

workspace "Hybrid-Image-Editor" "C4 model for Hybrid-Image-Editor (HIE) C++ repository." {

    model {
        user = person "User" "Interacts with the C++ application."

        system = softwareSystem "Hybrid-Image-Editor" "C++ repository application." {
            cli = container "CLI Executable" "Command-line interface." "C++17"
            lib = container "Core Library" "C++ domain logic." "C++17"
        }

        user -> cli "Executes"
        cli -> lib "Calls"
    }

    views {
        systemContext system "SystemContext" {
            include *
            autoLayout
        }

        container system "Containers" {
            include *
            autoLayout
        }

        theme default
    }
}
