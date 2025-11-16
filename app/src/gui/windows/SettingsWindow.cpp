#include "windows/SettingsWindow.h" // Assumed path
#include "MainWindow.h"
#include "src/core/VaultManager.h"
#include "utils/IBaseTab.h" // <-- The required interface

#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QFormLayout>
#include <QGroupBox>
#include <QLabel>
#include <QLineEdit>
#include <QRadioButton>
#include <QPushButton>
#include <QComboBox>
#include <QTextEdit>
#include <QScrollArea>
#include <QMessageBox>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonArray>
#include <QMetaProperty> // For metaObject()->className()
#include <QDynamicPropertyChangeEvent>

SettingsWindow::SettingsWindow(MainWindow *parent)
    // The parent is the MainWindow, but this widget is a standalone Window
    : QWidget(nullptr, Qt::Window), 
      m_main_window_ref(parent),
      m_vault_manager(nullptr),
      m_current_account_name("N/A")
{
    setWindowTitle("Application Settings");
    setMinimumSize(950, 950);

    // Get Vault Manager from main window
    if (m_main_window_ref) {
        m_vault_manager = m_main_window_ref->vault_manager;
    }

    // Load initial credentials
    if (m_vault_manager) {
        try {
            QJsonObject creds = m_vault_manager->load_account_credentials();
            m_current_account_name = creds.value("account_name").toString("N/A");
        } catch (...) {
            // Handle exception (e.g., file not found, decrypt error)
        }
    }

    // --- Configuration Defaults State ---
    m_tab_defaults_config = _load_tab_defaults_from_vault();

    QVBoxLayout *main_layout = new QVBoxLayout(this);
    main_layout->setContentsMargins(0, 0, 0, 0); // Full window layout

    // Determine initial styles
    bool is_light_theme = m_main_window_ref && m_main_window_ref->current_theme == "light";
    QString header_widget_bg = is_light_theme ? "#ffffff" : "#2d2d30";
    QString header_label_color = is_light_theme ? "#1e1e1e" : "white";
    QString accent_color = is_light_theme ? "#007AFF" : "#00bcd4";

    // --- Header Bar ---
    QWidget *header_widget = new QWidget;
    header_widget->setObjectName("header_widget");
    header_widget->setStyleSheet(QString("background-color: %1; padding: 10px; border-bottom: 2px solid %2;")
                                 .arg(header_widget_bg, accent_color));
    QHBoxLayout *header_layout = new QHBoxLayout(header_widget);
    header_layout->setContentsMargins(10, 5, 10, 5);
    
    QLabel *title_label = new QLabel("Application Settings");
    title_label->setStyleSheet(QString("color: %1; font-size: 14pt; font-weight: bold;")
                               .arg(header_label_color));
    header_layout->addWidget(title_label);
    header_layout->addStretch(1); 
    main_layout->addWidget(header_widget);
    // --- End Header Bar ---

    // --- Scrollable Content Area ---
    QScrollArea *content_scroll = new QScrollArea;
    content_scroll->setWidgetResizable(true);
    QWidget *content_container = new QWidget;
    QVBoxLayout *content_layout = new QVBoxLayout(content_container);
    content_layout->setContentsMargins(20, 20, 20, 20);
    content_layout->setAlignment(Qt::AlignTop);

    // --- Login Information Section ---
    QGroupBox *login_groupbox = new QGroupBox("Login/Account Information (Master Password Reset)");
    login_groupbox->setSizePolicy(QSizePolicy::Preferred, QSizePolicy::Fixed);
    QFormLayout *login_layout = new QFormLayout(login_groupbox);
    login_layout->setContentsMargins(10, 10, 10, 10);
    
    m_account_input = new QLineEdit;
    m_account_input->setReadOnly(true); 
    m_account_input->setText(m_current_account_name);
    
    m_new_password_input = new QLineEdit;
    m_new_password_input->setEchoMode(QLineEdit::Password);
    m_new_password_input->setPlaceholderText("Enter NEW Master Password to reset");
    
    login_layout->addRow(new QLabel("Account Name:"), m_account_input);
    login_layout->addRow(new QLabel("New Master Password:"), m_new_password_input);
    content_layout->addWidget(login_groupbox);
    
    // --- Preferences Section ---
    QGroupBox *prefs_groupbox = new QGroupBox("Preferences");
    prefs_groupbox->setSizePolicy(QSizePolicy::Preferred, QSizePolicy::Fixed);
    QVBoxLayout *prefs_layout = new QVBoxLayout(prefs_groupbox);
    prefs_layout->setContentsMargins(10, 10, 10, 10);
    
    m_dark_theme_radio = new QRadioButton("Dark Theme");
    m_light_theme_radio = new QRadioButton("Light Theme");
    
    if (is_light_theme) {
        m_light_theme_radio->setChecked(true);
    } else {
        m_dark_theme_radio->setChecked(true);
    }
    
    prefs_layout->addWidget(m_dark_theme_radio);
    prefs_layout->addWidget(m_light_theme_radio);
    content_layout->addWidget(prefs_groupbox);

    // --- Tab Default Configuration Section ---
    QGroupBox *defaults_groupbox = new QGroupBox("Tab Default Configuration Management");
    defaults_groupbox->setSizePolicy(QSizePolicy::Preferred, QSizePolicy::Expanding);
    QVBoxLayout *defaults_layout = new QVBoxLayout(defaults_groupbox);
    
    // 1. Tab Selection
    QFormLayout *tab_select_layout = new QFormLayout;
    m_tab_select_combo = new QComboBox;
    m_tab_select_combo->setPlaceholderText("Select a Tab...");
    QStringList tab_names = _get_all_tab_names();
    m_tab_select_combo->addItems(QStringList() << "" << tab_names);
    connect(m_tab_select_combo, &QComboBox::currentTextChanged, this, &SettingsWindow::_refresh_config_dropdown);
    tab_select_layout->addRow("Select Tab Class:", m_tab_select_combo);
    defaults_layout->addLayout(tab_select_layout);
    
    // 2. Load Existing Configuration
    QFormLayout *load_config_layout = new QFormLayout;
    m_config_select_combo = new QComboBox;
    m_config_select_combo->setPlaceholderText("Load/Edit Existing Config...");
    connect(m_config_select_combo, &QComboBox::currentTextChanged, this, &SettingsWindow::_load_selected_tab_config);
    load_config_layout->addRow("Load/Edit Config:", m_config_select_combo);
    
    QHBoxLayout *full_width_buttons_layout = new QHBoxLayout;
    full_width_buttons_layout->setContentsMargins(0, 5, 0, 5);
    full_width_buttons_layout->setSpacing(10);

    m_btn_set_config = new QPushButton("Set Selected Config");
    connect(m_btn_set_config, &QPushButton::clicked, this, &SettingsWindow::_set_selected_tab_config);
    m_btn_set_config->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Fixed);
    full_width_buttons_layout->addWidget(m_btn_set_config);
    
    m_btn_delete_config = new QPushButton("Delete Selected Config");
    m_btn_delete_config->setStyleSheet("background-color: #e74c3c; color: white;");
    connect(m_btn_delete_config, &QPushButton::clicked, this, &SettingsWindow::_delete_selected_tab_config);
    m_btn_delete_config->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Fixed);
    full_width_buttons_layout->addWidget(m_btn_delete_config);
    
    defaults_layout->addLayout(load_config_layout);
    defaults_layout->addLayout(full_width_buttons_layout);

    // 3. Create/Edit Configuration
    QGroupBox *create_config_group = new QGroupBox("Create/Edit Configuration");
    QFormLayout *create_config_layout = new QFormLayout(create_config_group);
    
    m_config_name_input = new QLineEdit;
    m_config_name_input->setPlaceholderText("Enter a unique name (e.g., HighResConfig)");
    create_config_layout->addRow("Config Name:", m_config_name_input);
    
    m_default_config_editor = new QTextEdit;
    m_default_config_editor->setPlaceholderText("Enter current tab settings as JSON here...");
    m_default_config_editor->setMinimumHeight(200);
    create_config_layout->addRow("Configuration (JSON):", m_default_config_editor);

    m_btn_create_default = new QPushButton("Save/Update Named Configuration");
    connect(m_btn_create_default, &QPushButton::clicked, this, &SettingsWindow::_save_current_tab_config);
    create_config_layout->addRow(m_btn_create_default);
    
    defaults_layout->addWidget(create_config_group);
    content_layout->addWidget(defaults_groupbox);
    
    content_layout->addStretch(1);
    content_scroll->setWidget(content_container);
    main_layout->addWidget(content_scroll); 

    // --- Action Buttons at the bottom ---
    QWidget *actions_widget = new QWidget;
    actions_widget->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Fixed);
    
    QHBoxLayout *actions_layout = new QHBoxLayout(actions_widget);
    actions_layout->setContentsMargins(20, 10, 20, 20);
    actions_layout->setSpacing(10);
    
    m_reset_button = new QPushButton("Reset to default");
    m_reset_button->setObjectName("reset_button");
    connect(m_reset_button, &QPushButton::clicked, this, &SettingsWindow::reset_settings);
    m_reset_button->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Fixed);
    
    m_update_button = new QPushButton("Update settings");
    m_update_button->setObjectName("update_button");
    connect(m_update_button, &QPushButton::clicked, this, &SettingsWindow::confirm_update_settings);
    m_update_button->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Fixed);
    m_update_button->setDefault(True);

    actions_layout->addWidget(m_reset_button);
    actions_layout->addWidget(m_update_button);
    main_layout->addWidget(actions_widget);
}

// --- Configuration Management Methods ---

QStringList SettingsWindow::_get_all_tab_names()
{
    QMap<QString, bool> tab_map;
    if (!m_main_window_ref) {
        return QStringList();
    }
        
    for (const auto& sub_tabs : m_main_window_ref->all_tabs) {
        for (QWidget* tab_instance : sub_tabs) {
            QString class_name = tab_instance->metaObject()->className();
            if (!tab_map.contains(class_name)) {
                tab_map[class_name] = true;
            }
        }
    }
    
    QStringList names = tab_map.keys();
    std::sort(names.begin(), names.end());
    return names;
}

QJsonObject SettingsWindow::_load_tab_defaults_from_vault()
{
    if (!m_vault_manager) {
        return QJsonObject();
    }
    try {
        QJsonObject full_data = m_vault_manager->load_account_credentials();
        QString tab_defaults_json = full_data.value("tab_defaults").toString("{}");
        
        QJsonDocument doc = QJsonDocument::fromJson(tab_defaults_json.toUtf8());
        if (doc.isObject()) {
            return doc.object();
        }
        return QJsonObject();
    } catch (...) {
        qWarning("Failed to load tab defaults from vault");
        return QJsonObject();
    }
}

bool SettingsWindow::_save_tab_defaults_to_vault()
{
    if (!m_vault_manager) {
        QMessageBox::critical(this, "Save Error", "Vault manager is not available to save settings.");
        return false;
    }

    try {
        QJsonObject user_data = m_vault_manager->load_account_credentials();
        
        // Convert QJsonObject to compact JSON string
        user_data["tab_defaults"] = QJsonDocument(m_tab_defaults_config).toJson(QJsonDocument::Compact);
        
        // Save the full user data object back
        m_vault_manager->save_data(QJsonDocument(user_data).toJson(QJsonDocument::Compact));
        return true;
    } catch (...) {
        QMessageBox::critical(this, "Save Error", "Failed to save tab configurations to vault.");
        return false;
    }
}

void SettingsWindow::_refresh_config_dropdown(const QString &tab_class_name)
{
    // Disconnect slot to prevent firing while we repopulate
    disconnect(m_config_select_combo, &QComboBox::currentTextChanged, this, &SettingsWindow::_load_selected_tab_config);
        
    m_config_select_combo->clear();
    m_config_name_input->clear();
    m_default_config_editor->clear();
    m_current_loaded_config_name.clear();

    if (tab_class_name.isEmpty()) {
        m_config_select_combo->setPlaceholderText("Select a Tab Class first.");
    } else {
        // Get configs for this class
        QJsonObject configs = m_tab_defaults_config.value(tab_class_name).toObject();
        QStringList config_names = configs.keys();
        std::sort(config_names.begin(), config_names.end());
        
        m_config_select_combo->addItems(QStringList() << "" << config_names);
        m_config_select_combo->setPlaceholderText("Load/Edit Existing Config...");
    }

    // Reconnect slot
    connect(m_config_select_combo, &QComboBox::currentTextChanged, this, &SettingsWindow::_load_selected_tab_config);
}

void SettingsWindow::_load_selected_tab_config(const QString &config_name)
{
    QString tab_class_name = m_tab_select_combo->currentText();
    
    if (tab_class_name.isEmpty() || config_name.isEmpty()) {
        m_config_name_input->clear();
        m_default_config_editor->clear();
        m_current_loaded_config_name.clear();
        return;
    }

    QJsonObject configs = m_tab_defaults_config.value(tab_class_name).toObject();
    QJsonObject config = configs.value(config_name).toObject();
    
    try {
        QString json_str = QJsonDocument(config).toJson(QJsonDocument::Indented);
        m_default_config_editor->setText(json_str);
        m_config_name_input->setText(config_name);
        m_current_loaded_config_name = config_name;
    } catch (...) {
        QMessageBox::critical(this, "Load Error", QString("Failed to load config '%1'").arg(config_name));
    }
}

void SettingsWindow::_save_current_tab_config()
{
    QString tab_class_name = m_tab_select_combo->currentText();
    QString config_name = m_config_name_input->text().trimmed();
    QString json_text = m_default_config_editor->toPlainText().trimmed();
    
    if (tab_class_name.isEmpty() || config_name.isEmpty()) {
        QMessageBox::warning(this, "Input Error", "Please select a Tab Class and provide a Config Name.");
        return;
    }

    if (json_text.isEmpty()) {
        QMessageBox::warning(this, "Input Error", "Configuration JSON cannot be empty.");
        return;
    }

    try {
        QJsonParseError error;
        QJsonDocument doc = QJsonDocument::fromJson(json_text.toUtf8(), &error);
        
        if (doc.isNull()) {
            throw std::runtime_error(error.errorString().toStdString().c_str());
        }
        if (!doc.isObject()) {
            throw std::runtime_error("Configuration must be a valid JSON object.");
        }

        QJsonObject new_config = doc.object();
        
        // Get or create the object for this tab class
        QJsonObject tab_configs = m_tab_defaults_config.value(tab_class_name).toObject();
        // Insert/update the named config
        tab_configs[config_name] = new_config;
        // Put it back into the main config object
        m_tab_defaults_config[tab_class_name] = tab_configs;
        
        if (_save_tab_defaults_to_vault()) {
            QMessageBox::information(this, "Success", QString("Configuration '%1' saved for %2.").arg(config_name, tab_class_name));
            
            _refresh_config_dropdown(tab_class_name);
            m_config_select_combo->setCurrentText(config_name);
        }
        
    } catch (const std::runtime_error& e) {
        QMessageBox::critical(this, "JSON Error", QString("Invalid JSON format:\n%1").arg(e.what()));
    } catch (...) {
        QMessageBox::critical(this, "Error", "An unexpected error occurred during save.");
    }
}

void SettingsWindow::_delete_selected_tab_config()
{
    QString tab_class_name = m_tab_select_combo->currentText();
    QString config_name = m_config_select_combo->currentText();
    
    if (tab_class_name.isEmpty() || config_name.isEmpty()) {
        QMessageBox::warning(this, "Delete Error", "Please select a tab class and a configuration to delete.");
        return;
    }

    auto reply = QMessageBox::question(this, "Confirm Deletion", 
        QString("Are you sure you want to PERMANENTLY delete the configuration '%1'?").arg(config_name),
        QMessageBox::Yes | QMessageBox::No, 
        QMessageBox::No);

    if (reply == QMessageBox::Yes) {
        try {
            if (m_tab_defaults_config.contains(tab_class_name)) {
                QJsonObject tab_configs = m_tab_defaults_config.value(tab_class_name).toObject();
                if (tab_configs.contains(config_name)) {
                    tab_configs.remove(config_name);
                    
                    if (tab_configs.isEmpty()) {
                        // Remove the whole tab class entry if no configs are left
                        m_tab_defaults_config.remove(tab_class_name);
                    } else {
                        // Otherwise, just update the tab's config object
                        m_tab_defaults_config[tab_class_name] = tab_configs;
                    }
                        
                    if (_save_tab_defaults_to_vault()) {
                        QMessageBox::information(this, "Success", QString("Configuration '%1' deleted.").arg(config_name));
                        m_config_name_input->clear();
                        m_default_config_editor->clear();
                        _refresh_config_dropdown(tab_class_name);
                    }
                }
            }
        } catch (...) {
            QMessageBox::critical(this, "Delete Error", "Failed to delete configuration.");
        }
    }
}

void SettingsWindow::_set_selected_tab_config()
{
    QString tab_class_name = m_tab_select_combo->currentText();
    QString config_name = m_config_name_input->text().trimmed();
    QString json_text = m_default_config_editor->toPlainText().trimmed();
    
    if (tab_class_name.isEmpty() || config_name.isEmpty() || json_text.isEmpty()) {
        QMessageBox::warning(this, "Set Error", "Please load or create a valid configuration first.");
        return;
    }
        
    try {
        QJsonParseError error;
        QJsonDocument doc = QJsonDocument::fromJson(json_text.toUtf8(), &error);
        if (doc.isNull() || !doc.isObject()) {
            throw std::runtime_error(error.errorString().toStdString().c_str());
        }
        QJsonObject config_data = doc.object();
        
        QWidget* target_tab_instance = nullptr;
        if (m_main_window_ref) {
            for (const auto& sub_tabs : m_main_window_ref->all_tabs) {
                for (QWidget* tab_instance : sub_tabs) {
                    if (tab_instance->metaObject()->className() == tab_class_name) {
                        target_tab_instance = tab_instance;
                        break;
                    }
                }
                if (target_tab_instance) break;
            }
        }

        if (!target_tab_instance) {
            QMessageBox::critical(this, "Set Error", QString("Could not find active instance of tab: %1.").arg(tab_class_name));
            return;
        }

        // --- This is the C++ 'hasattr' check ---
        // Try to dynamically cast the QWidget* to an IBaseTab*
        IBaseTab* tab_interface = dynamic_cast<IBaseTab*>(target_tab_instance);
        
        if (tab_interface) {
            // Success! The tab implements the interface.
            tab_interface->set_config(config_data);
            QMessageBox::information(this, "Success", QString("Configuration '%1' applied to %2.").arg(config_name, tab_class_name));
        } else {
            // Failure. The tab was found, but it does not inherit from IBaseTab.
            QMessageBox::critical(this, "Set Error", 
                QString("Target tab '%1' does not implement the 'IBaseTab' interface and cannot be configured.")
                .arg(tab_class_name));
        }

    } catch (const std::runtime_error& e) {
        QMessageBox::critical(this, "JSON Error", QString("Invalid JSON in editor. Cannot apply configuration:\n%1").arg(e.what()));
    } catch (...) {
        QMessageBox::critical(this, "Error", "An unexpected error occurred during configuration application.");
    }
}

// --- Other Settings Methods ---

void SettingsWindow::confirm_update_settings()
{
    auto reply = QMessageBox::question(this, "Confirm Update", 
        "Are you sure you want to update the app's settings?",
        QMessageBox::Yes | QMessageBox::No, 
        QMessageBox::No);

    if (reply == QMessageBox::Yes) {
        _update_settings_logic();
    }
}

void SettingsWindow::_update_settings_logic()
{
    QString new_password = m_new_password_input->text().trimmed();
    
    // --- Handle Password Change (Master Reset) ---
    if (!new_password.isEmpty()) {
        if (!m_vault_manager) {
            QMessageBox::critical(this, "Update Failed", "Vault manager is not available.");
            return;
        }

        try {
            m_vault_manager->update_account_password(
                m_current_account_name, 
                new_password
            );
            
            if (m_main_window_ref) {
                m_main_window_ref->update_header();
            }
            
            QMessageBox::information(this, "Success", "Master password successfully updated! All data was preserved.");
            
        } catch (...) {
            QMessageBox::critical(this, "Update Failed", "Failed to update master password.");
            return;
        }
    }
    
    // --- Handle Theme Change ---
    QString selected_theme = m_dark_theme_radio->isChecked() ? "dark" : "light";

    if (m_main_window_ref) {
        m_main_window_ref->set_application_theme(selected_theme);
    }
        
    this->close();
}

void SettingsWindow::reset_settings()
{
    m_new_password_input->clear();
    m_dark_theme_radio->setChecked(true);
}