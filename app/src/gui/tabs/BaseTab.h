#pragma once

#include <QWidget>
#include <QStringList>
#include <QJsonObject>
#include "IBaseTab.h" // <-- Required interface

/**
 * @brief Abstract base class for all tabs in the application.
 *
 * Inherits from QWidget for UI and IBaseTab to allow for
 * runtime configuration from the SettingsWindow.
 */
class BaseTab : public QWidget, public IBaseTab
{
    Q_OBJECT

public:
    explicit BaseTab(QWidget *parent = nullptr);
    virtual ~BaseTab() {}

    // --- IBaseTab Implementation ---
    /**
     * @brief Default implementation for set_config.
     * Tabs that are configurable must override this method.
     */
    void set_config(const QJsonObject& config) override;

    // --- Pure Virtual Methods ---
    // These must be implemented by all derived tab classes.
    virtual void browse_files() = 0;
    virtual void browse_directory() = 0;
    virtual void browse_input() = 0;
    virtual void browse_output() = 0;

    // --- Virtual Methods (Optional) ---
    /**
     * @brief Collects configuration/inputs from the tab.
     * @return A QJsonObject representing the tab's current state.
     */
    virtual QJsonObject collect();

    // --- Static Helpers ---
    /**
     * @brief Convert a comma/space separated string to list of strings.
     */
    static QStringList join_list_str(const QString &s);
};