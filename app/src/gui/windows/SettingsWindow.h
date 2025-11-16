#pragma once

#include <QWidget>
#include <QJsonObject>

// Forward declarations
class MainWindow; 
class JavaVaultManager; 
class QLineEdit;
class QRadioButton;
class QComboBox;
class QTextEdit;
class QPushButton;

class SettingsWindow : public QWidget
{
    Q_OBJECT

public:
    // Takes a pointer to the MainWindow
    explicit SettingsWindow(MainWindow *parent = nullptr);

private slots:
    // Config management
    void _refresh_config_dropdown(const QString &tab_class_name);
    void _load_selected_tab_config(const QString &config_name);
    void _save_current_tab_config();
    void _delete_selected_tab_config();
    void _set_selected_tab_config();

    // Main actions
    void confirm_update_settings();
    void reset_settings();

private:
    void _update_settings_logic();
    
    // Helper methods
    QStringList _get_all_tab_names();
    QJsonObject _load_tab_defaults_from_vault();
    bool _save_tab_defaults_to_vault();

    // Class members
    MainWindow *m_main_window_ref; // Reference to the main window
    JavaVaultManager *m_vault_manager;
    QString m_current_account_name;
    
    // State for default configs
    QJsonObject m_tab_defaults_config;
    QString m_current_loaded_config_name;

    // UI Widgets
    QLineEdit *m_account_input;
    QLineEdit *m_new_password_input;
    QRadioButton *m_dark_theme_radio;
    QRadioButton *m_light_theme_radio;
    QComboBox *m_tab_select_combo;
    QComboBox *m_config_select_combo;
    QPushButton *m_btn_set_config;
    QPushButton *m_btn_delete_config;
    QLineEdit *m_config_name_input;
    QTextEdit *m_default_config_editor;
    QPushButton *m_btn_create_default;
    QPushButton *m_reset_button;
    QPushButton *m_update_button;
};