#-------------------------------------------------
# Project Configuration
#-------------------------------------------------
# Based on the file names (workers, windows, widgets), 
# we need core, gui, and widgets.
# The GoogleDriveSyncWorker implies network capabilities.
QT       += core gui widgets network

# Set the C++ standard (C++17 is a good modern default)
CONFIG   += c++17

# The name of your final executable
TARGET    = ImageToolkit

# This project builds an application (executable)
TEMPLATE  = app

#-------------------------------------------------
# Include Path
#-------------------------------------------------
# Add the project's root directory to the include path.
# This allows you to use #include "components/ClickableLabel.h"
INCLUDEPATH += .

#-------------------------------------------------
# Source Files
#-------------------------------------------------
SOURCES += \
    MainWindow.cpp \
    \
    components/ClickableLabel.cpp \
    components/DraggableImageLabel.cpp \
    components/ImagePreviewWindow.cpp \
    components/MarqueeScrollArea.cpp \
    components/MonitorDropWidget.cpp \
    components/OptionalField.cpp \
    components/QueueItemWidget.cpp \
    \
    styles/Style.cpp \
    \
    windows/LoginWindow.cpp \
    windows/LogWindow.cpp \
    windows/SettingsWindow.cpp \
    windows/SlideshowQueueWindow.cpp \
    \
    helpers/BatchThumbnailLoaderWorker.cpp \
    helpers/ConversionWorker.cpp \
    helpers/DeletionWorker.cpp \
    helpers/GoogleDriveSyncWorker.cpp \
    helpers/ImageCrawlWorker.cpp \
    helpers/ImageScannerWorker.cpp \
    helpers/MergeWorker.cpp \
    helpers/WallpaperWorker.cpp \
    \
    tabs/BaseTab.cpp \
    tabs/ConvertTab.cpp \
    tabs/DatabaseTab.cpp \
    tabs/DeleteTab.cpp \
    tabs/DriveSyncTab.cpp \
    tabs/ImageCrawlTab.cpp \
    tabs/MergeTab.cpp \
    tabs/ScanMetadataTab.cpp \
    tabs/SearchTab.cpp \
    tabs/WallpaperTab.cpp

#-------------------------------------------------
# Header Files
#-------------------------------------------------
HEADERS += \
    MainWindow.h \
    \
    components/ClickableLabel.h \
    components/DraggableImageLabel.h \
    components/ImagePreviewWindow.h \
    components/MarqueeScrollArea.h \
    components/MonitorDropWidget.h \
    components/OptionalField.h \
    components/QueueItemWidget.h \
    \
    styles/Style.h \
    \
    utils/AppDefinitions.h \
    utils/IBaseTab.h \
    \
    windows/LoginWindow.h \
    windows/LogWindow.h \
    windows/SettingsWindow.h \
    windows/SlideshowQueueWindow.h \
    \
    helpers/BatchThumbnailLoaderWorker.h \
    helpers/ConversionWorker.h \
    helpers/DeletionWorker.h \
    helpers/GoogleDriveSyncWorker.h \
    helpers/ImageCrawlWorker.h \
    helpers/ImageScannerWorker.h \
    helpers/MergeWorker.h \
    helpers/WallpaperWorker.h \
    \
    tabs/BaseTab.h \
    tabs/ConvertTab.h \
    tabs/DatabaseTab.h \
    tabs/DeleteTab.h \
    tabs/DriveSyncTab.h \
    tabs/ImageCrawlTab.h \
    tabs/MergeTab.h \
    tabs/ScanMetadataTab.h \
    tabs/SearchTab.h \
    tabs/WallpaperTab.h