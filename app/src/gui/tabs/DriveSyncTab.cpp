#pragma once

#include "tabs/BaseTab.h"
#include <QJsonObject>

// Forward Declarations
class LogWindow;
class GoogleDriveSyncWorker;
class QComboBox;
class QLineEdit;
class QPushButton;
class QCheckBox;
class QLabel;

class DriveSyncTab : public BaseTab
{
    Q_OBJECT

public:
    explicit DriveSyncTab(bool dropdown = true, QWidget *parent = nullptr);
    ~DriveSyncTab();

    // --- BaseTab Overrides ---
    void browse_files() override;
    void browse_directory() override;
    void browse_input() override;
    void browse_output() override;
    QJsonObject collect() override;
    // set_config(const QJsonObject& config) override; // <-- Uncomment and implement if this tab is configurable

private slots:
    void toggle_sync();
    void stop_sync_now();
    void handle_provider_change(int index);
    
    void view_remote_map();
    void handle_view_finished(bool success, const QString& message);
    
    void share_remote_folder();
    void handle_share_finished(bool success, const QString& message);

    void run_sync_now(bool clear_log = true);
    
    void handle_status_update(const QString& msg);
    void handle_sync_finished(bool success, const QString& message);

    // --- Browsers ---
    void browse_key_file();
    void browse_client_secrets_file();
    void browse_local_directory();

private:
    void init_ui();
    bool build_auth_config(QJsonObject &auth_config);
    void load_configuration_defaults();
    
    void lock_ui(const QString& message, bool is_running = false, bool clear_log = false);
    void unlock_ui();
    void lock_ui_minor(const QString& message, bool clear_log = false);
    void unlock_ui_minor();

    LogWindow* m_log_window;
    GoogleDriveSyncWorker* m_current_worker;

    // --- UI Widgets ---
    QComboBox* m_provider_combo;
    
    QLabel* m_key_file_label;
    QLineEdit* m_key_file_path;
    QPushButton* m_btn_browse_key;
    
    QLabel* m_client_secrets_label;
    QLineEdit* m_client_secrets_path;
    QPushButton* m_btn_browse_client_secrets;
    
    QLabel* m_token_file_label;
    QLineEdit* m_token_file_path;
    
    QLineEdit* m_local_path;
    QLineEdit* m_remote_path;
    
    QLabel* m_share_email_label;
    QLineEdit* m_share_email_input;
    
    QPushButton* m_btn_view_remote;
    QPushButton* m_btn_share_folder;
    QCheckBox* m_dry_run_checkbox;
    QPushButton* m_sync_button;
};