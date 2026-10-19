workspace "Cel-Shaded-Generator" "Offline anime learning and cel-shaded art application." {
    model {
        artist = person "Artist/Learner" "Learns and creates cel-shaded artwork offline."
        system = softwareSystem "Cel-Shaded-Generator" "Krita-first tutor and future desktop editor." {
            krita = container "Krita Plugin" "Guided lessons, exercises, and accepted suggestions." "Python / Krita"
            gui = container "Desktop GUI" "Current solver demonstration; future editor shell." "PySide6"
            core = container "Core" "Projects, teaching contracts, and algorithm orchestration." "Python"
            workers = container "Isolated Workers" "Crash-contained native numerical jobs." "Spawned Python processes"
            engine = container "Future Engine" "Measured performance-critical implementation." "C++"
        }
        artist -> krita "Practises and requests review"
        artist -> gui "Uses standalone tools"
        krita -> core "Uses public contracts"
        gui -> core "Uses public contracts"
        core -> workers "Dispatches serializable operations"
        core -> engine "Future stable bindings"
    }
    views {
        systemContext system "Context" { include *; autoLayout lr }
        container system "Containers" { include *; autoLayout lr }
        theme default
    }
}
