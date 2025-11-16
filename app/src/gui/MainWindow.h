#pragma once

#include <QWidget>
#include <QMap>
#include <QImageReader>

// Forward declarations
class JavaVaultManager;
class SettingsWindow;
class QTabWidget;
class QPushButton;
class QComboBox;
class QKeyEvent;
class QCloseEvent;
class DatabaseTab;
class SearchTab;
class ScanMetadataTab;
class ConvertTab;
class MergeTab;
class DeleteTab;
class ImageCrawlTab;
class DriveSyncTab;
class WallpaperTab;


class MainWindow : public QWidget
{
    Q_OBJECT

public:
    // Takes ownership of the vault_manager pointer
    explicit MainWindow(JavaVaultManager* vault_manager, 
                        bool dropdown = true, 
                        const QString& app_icon_path = QString(), 
                        QWidget* parent = nullptr);
    ~MainWindow();

    // Public members for SettingsWindow to access
    JavaVaultManager* vault_manager;
    QString current_theme;
    
    // Map of all tab instances, grouped by category
    QMap<QString, QMap<QString, QWidget*>> all_tabs;

public slots:
    void set_application_theme(const QString& theme_name);
    void update_header(); // Slot for SettingsWindow to call

protected:
    void keyPressEvent(QKeyEvent *event) override;
    void closeEvent(QCloseEvent *event) override;

private slots:
    void on_command_changed(const QString& new_command);
    void open_settings_window();
    void _reset_settings_window_ref();

private:
    void init_ui(bool dropdown, const QString& app_icon_path);
    void init_tabs(bool dropdown);

    // Tab instances
    DatabaseTab* m_database_tab;
    SearchTab* m_search_tab;
    ScanMetadataTab* m_scan_metadata_tab;
    ConvertTab* m_convert_tab;
    MergeTab* m_merge_tab;
    DeleteTab* m_delete_tab;
    ImageCrawlTab* m_crawler_tab;
    DriveSyncTab* m_drive_sync_tab;
    WallpaperTab* m_wallpaper_tab;

    // UI Widgets
    SettingsWindow* m_settings_window;
    QPushButton* m_settings_button;
    QComboBox* m_command_combo;
    QTabWidget* m_tabs;
    
    // From app_definitions.py
    const int NEW_LIMIT_MB = 1024; // Or load from definitions.h
};