#include "MainWindow.h"

// Core dependencies
#include "src/core/JavaVaultManager.h"

// Window dependencies
#include "windows/SettingsWindow.h" // Assumed path

// Tab dependencies (Assumed paths)
#include "tabs/WallpaperTab.h"
#include "tabs/MergeTab.h"
#include "tabs/DatabaseTab.h"
#include "tabs/ConvertTab.h"
#include "tabs/DeleteTab.h"
#include "tabs/ScanMetadataTab.h"
#include "tabs/SearchTab.h"
#include "tabs/ImageCrawlTab.h"
#include "tabs/DriveSyncTab.h"

// Styles
#include "styles/Style.h" // Assumed path, provides DARK_QSS and LIGHT_QSS

// Qt Includes
#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QLabel>
#include <QPushButton>
#include <QComboBox>
#include <QTabWidget>
#include <QIcon>
#include <QStyle>
#include <QApplication>
#include <QKeyEvent>
#include <QCloseEvent>
#include <QFileInfo>
#include <QImageReader>

MainWindow::MainWindow(JavaVaultManager* vault_manager, 
                       bool dropdown, 
                       const QString& app_icon_path, 
                       QWidget* parent)
    : QWidget(parent),
      vault_manager(vault_manager), // Take ownership of the pointer
      current_theme("dark"),
      m_settings_window(nullptr)
{
    setWindowTitle("Image Database & Edit Toolkit");
    setMinimumSize(950, 950);
    setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Expanding);
    
    // Assuming NEW_LIMIT_MB is defined in "src/utils/app_definitions.h"
    // If not, using the hardcoded value from .h
    // QImageReader::setAllocationLimit(app_definitions::NEW_LIMIT_MB);
    QImageReader::setAllocationLimit(NEW_LIMIT_MB); 

    init_tabs(dropdown);
    init_ui(dropdown, app_icon_path);

    // Apply theme after all widgets are initialized
    set_application_theme(current_theme);
}

MainWindow::~MainWindow()
{
    // MainWindow is responsible for shutting down and deleting
    // the vault_manager it received from LoginWindow.
    if (vault_manager) {
        vault_manager->shutdown();
        delete vault_manager;
    }
    // Qt's parent-child system will delete all child widgets
    // (layouts, tabs, buttons, etc.)
}

void MainWindow::init_tabs(bool dropdown)
{
    // Instantiate all sub-command tabs once
    m_database_tab = new DatabaseTab(dropdown, this);
    m_search_tab = new SearchTab(m_database_tab, dropdown, this);
    m_scan_metadata_tab = new ScanMetadataTab(m_database_tab, dropdown, this);
    m_convert_tab = new ConvertTab(dropdown, this);
    m_merge_tab = new MergeTab(dropdown, this);
    m_delete_tab = new DeleteTab(dropdown, this);
    m_crawler_tab = new ImageCrawlTab(dropdown, this);
    m_drive_sync_tab = new DriveSyncTab(dropdown, this);
    m_wallpaper_tab = new WallpaperTab(m_database_tab, dropdown, this);

    // Set references *after* all tabs are created
    m_database_tab->scan_tab_ref = m_scan_metadata_tab;
    m_database_tab->search_tab_ref = m_search_tab;

    // Define the hierarchical map
    all_tabs["System Tools"] = {
        {"Convert Format", m_convert_tab},
        {"Merge Images", m_merge_tab},
        {"Delete Images", m_delete_tab},
        {"Display Wallpaper", m_wallpaper_tab},
    };
    all_tabs["Database Management"] = {
        {"Database Configuration", m_database_tab},
        {"Search Images", m_search_tab},
        {"Scan Metadata", m_scan_metadata_tab},
    };
    all_tabs["Web Integration"] = {
        {"Web Crawler", m_crawler_tab},
        {"Cloud Synchronization", m_drive_sync_tab},
    };
}


void MainWindow::init_ui(bool dropdown, const QString& app_icon_path)
{
    QVBoxLayout* vbox = new QVBoxLayout(this);
    vbox->setContentsMargins(0,0,0,0);

    // --- Application Header ---
    QWidget* header_widget = new QWidget;
    header_widget->setObjectName("header_widget");
    QHBoxLayout* header_layout = new QHBoxLayout(header_widget);
    header_layout->setContentsMargins(10, 5, 10, 5);
    
    QString account_name = "Authenticated User";
    try {
        account_name = vault_manager->load_account_credentials().value("account_name").toString("Authenticated User");
    } catch (...) {
        // Ignore
    }
        
    QLabel* title_label = new QLabel(QString("Image Database and Toolkit - %1").arg(account_name));
    title_label->setObjectName("title_label"); // Give it a name for set_application_theme
    header_layout->addWidget(title_label);
    header_layout->addStretch(1); 
    
    // --- Settings button ---
    m_settings_button = new QPushButton;
    QIcon settings_icon;
    if (!app_icon_path.isEmpty() && QFileInfo::exists(app_icon_path)) {
        settings_icon.addFile(app_icon_path);
    } else {
        settings_icon = this->style()->standardIcon(QStyle::SP_ToolBarHorizontalExtensionButton);
    }
    m_settings_button->setIcon(settings_icon);
    m_settings_button->setIconSize(QSize(24, 24));
    m_settings_button->setFixedSize(QSize(36, 36));
    m_settings_button->setObjectName("settings_button");
    m_settings_button->setToolTip("Open Settings");
    m_settings_button->setDefault(true); 
    
    header_layout->addWidget(m_settings_button);
    vbox->addWidget(header_widget);
    
    // --- Command Selection (QComboBox) ---
    QHBoxLayout* command_layout = new QHBoxLayout;
    command_layout->setContentsMargins(10, 5, 10, 5); // Add some padding
    QLabel* command_label = new QLabel("Select Category:");
    command_label->setStyleSheet("font-weight: 600;");
    command_layout->addWidget(command_label);
    
    m_command_combo = new QComboBox;
    // Get keys from our map
    m_command_combo->addItems(all_tabs.keys());
    connect(m_command_combo, &QComboBox::currentTextChanged, this, &MainWindow::on_command_changed);
    m_command_combo->setSizePolicy(QSizePolicy::Preferred, QSizePolicy::Fixed);
    command_layout->addWidget(m_command_combo);
    command_layout->addStretch();
    vbox->addLayout(command_layout);
    
    // --- Tabs container ---
    m_tabs = new QTabWidget;
    vbox->addWidget(m_tabs);
    
    // Set initial content
    on_command_changed(m_command_combo->currentText());

    connect(m_settings_button, &QPushButton::clicked, this, &MainWindow::open_settings_window);
}


void MainWindow::on_command_changed(const QString& new_command)
{
    m_tabs->clear();
    
    // Get the map of tabs for the selected command category
    const auto& tab_map = all_tabs.value(new_command);
    
    // Add the tabs to the QTabWidget
    for (auto it = tab_map.begin(); it != tab_map.end(); ++it) {
        m_tabs->addTab(it.value(), it.key());
    }
}

void MainWindow::set_application_theme(const QString& theme_name)
{
    QString qss;
    QString hover_bg;
    QString pressed_bg;
    QString accent_color;
    QString header_label_color;
    QString header_widget_bg;

    if (theme_name == "dark") {
        qss = DARK_QSS; // Assumed from styles/style.h
        current_theme = "dark";
        hover_bg = "#5f646c";
        pressed_bg = "#00bcd4";
        accent_color = "#00bcd4";
        header_label_color = "white";
        header_widget_bg = "#2d2d30";
    } else if (theme_name == "light") {
        qss = LIGHT_QSS; // Assumed from styles/style.h
        current_theme = "light";
        hover_bg = "#cccccc";
        pressed_bg = "#007AFF";
        accent_color = "#007AFF";
        header_label_color = "#1e1e1e";
        header_widget_bg = "#ffffff";
    } else {
        return;
    }
        
    QApplication::instance()->setStyleSheet(qss);
    
    // --- Header Widget (The bar itself) ---
    QWidget* header_widget = this->findChild<QWidget*>("header_widget");
    if (header_widget) {
        header_widget->setStyleSheet(QString(
            "background-color: %1; padding: 10px; border-bottom: 2px solid %2;"
        ).arg(header_widget_bg, accent_color));
        
        // --- Header Label ---
        update_header(); // Call helper to update text and color
    }

    // Re-apply the settings button style
    m_settings_button->setStyleSheet(QString(R"(
        QPushButton#settings_button {
            background-color: transparent;
            border: none;
            padding: 5px;
            border-radius: 18px; 
        }
        QPushButton#settings_button:hover {
            background-color: %1; 
        }
        QPushButton#settings_button:pressed {
            background-color: %2; 
        }
    )").arg(hover_bg, pressed_bg));
}

void MainWindow::update_header()
{
    QWidget* header_widget = this->findChild<QWidget*>("header_widget");
    if (!header_widget) return;
    
    QLabel* title_label = header_widget->findChild<QLabel*>("title_label");
    if (!title_label) return;

    QString header_label_color = (current_theme == "light") ? "#1e1e1e" : "white";

    QString account_name = "Authenticated User";
    try {
        account_name = vault_manager->load_account_credentials().value("account_name").toString("Authenticated User");
    } catch (...) {
        // ignore
    }
        
    title_label->setText(QString("Image Database and Toolkit - %1").arg(account_name));
    title_label->setStyleSheet(QString(
        "color: %1; font-size: 18pt; font-weight: bold;"
    ).arg(header_label_color));
}


void MainWindow::open_settings_window()
{
    if (!m_settings_window) {
        m_settings_window = new SettingsWindow(this); // 'this' is the parent
        m_settings_window->setAttribute(Qt::WA_DeleteOnClose);
        // Use slot to reset pointer when window is destroyed
        connect(m_settings_window, &QObject::destroyed, this, &MainWindow::_reset_settings_window_ref);
    }
    m_settings_window->show();
    m_settings_window->activateWindow();
}

void MainWindow::_reset_settings_window_ref()
{
    m_settings_window = nullptr;
}

void MainWindow::keyPressEvent(QKeyEvent *event)
{
    if (event->key() == Qt::Key_Escape) {
        // vault_manager shutdown is handled in ~MainWindow() via close()
        QApplication::quit();
    } else {
        QWidget::keyPressEvent(event);
    }
}

void MainWindow::closeEvent(QCloseEvent *event)
{
    // The destructor (~MainWindow) will handle the shutdown.
    // We just accept the event.
    QWidget::closeEvent(event);
}