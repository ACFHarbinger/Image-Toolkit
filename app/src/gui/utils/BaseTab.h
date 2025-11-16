#pragma once

#include <QJsonObject>

/**
 * @brief
 * This interface is the C++ equivalent of Python's dynamic 'hasattr(tab, "set_config")'.
 *
 * In C++, we cannot check for a method's existence at runtime like in Python.
 * Instead, any tab that wishes to be configurable by the SettingsWindow MUST
 * publicly inherit from this class and implement the pure virtual `set_config` function.
 *
 * Example:
 * class MyTab : public QWidget, public IBaseTab { ... }
 */
class BaseTab
{
public:
    // Virtual destructor is required for a base class
    virtual ~BaseTab() {}

    /**
     * @brief Applies a given configuration to the tab.
     * @param config A QJsonObject containing the settings to apply.
     */
    virtual void set_config(const QJsonObject& config) = 0;
};