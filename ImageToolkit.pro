# This is the main, parent project file.
# It uses the SUBDIRS template to build projects located in child directories.

# Use the SUBDIRS template for a top-level project file
TEMPLATE = subdirs

# List the subdirectories that contain other project files (.pro)
# Note: The path is relative to this file's location (the root).
SUBDIRS += \
    app/src/gui

# You can optionally specify the order of building (if dependencies exist)
# CONFIG += ordered

# Configuration options for all subprojects (optional)
# CONFIG += c++17 debug_and_release