# env/cpp/qt_app.pro
# Qt project definition file with GUI dependencies.

TEMPLATE = app
TARGET = PolyglotCppApp

QT += core gui widgets

CONFIG += c++17

SOURCES += main.cpp
HEADERS += main.h

# Install paths
target.path = $$[QT_INSTALL_BINS]
INSTALLS += target
