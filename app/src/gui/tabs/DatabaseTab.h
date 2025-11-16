#pragma once

#include "tabs/BaseTab.h" // Assumed path
#include <QJsonObject>

// Forward Declarations
class PgvectorImageDatabase;
class ScanMetadataTab;
class SearchTab;
class QLineEdit;
class QPushButton;
class QLabel;
class QTableWidget;
class QComboBox;
class QGroupBox;
class QTableWidgetItem;
class QPoint;

class DatabaseTab : public BaseTab
{
    Q_OBJECT

public:
    explicit DatabaseTab(bool dropdown = true, const QString& env_path = "env/vars.env", QWidget *parent = nullptr);
    ~DatabaseTab();

    // --- Public Members (for other tabs) ---
    PgvectorImageDatabase* db;
    ScanMetadataTab* scan_tab_ref;
    SearchTab* search_tab_ref;
    
    // --- BaseTab Overrides ---
    void browse_files() override;
    void browse_directory() override;
    void browse_input() override;
    void browse_output() override;
    QJsonObject collect() override;
    // set_config(const QJsonObject& config) override; // <-- Uncomment and implement if this tab is configurable

public slots:
    // --- Public Slots (for other tabs) ---
    void update_statistics();
    void _refresh_all_group_combos();
    void refresh_subgroup_autocomplete();
    void refresh_tags_list();
    void refresh_groups_list();
    void refresh_subgroups_list();

private slots:
    // --- Connection ---
    void connect_database();
    void disconnect_database();
    void reset_database();

    // --- Creation ---
    void create_new_group();
    void create_new_subgroup();
    void create_new_tag();

    // --- Deletion ---
    void remove_selected_group();
    void remove_selected_subgroup();
    void remove_selected_tag();
    
    // --- Table Editing ---
    void store_old_value(int row, int col);
    void handle_group_edited(QTableWidgetItem *item);
    void handle_subgroup_edited(QTableWidgetItem *item);
    void handle_tag_edited(QTableWidgetItem *item);
    
    // --- Context Menus ---
    void show_group_context_menu(const QPoint &pos);
    void edit_selected_group_cell();
    void show_subgroup_context_menu(const QPoint &pos);
    void edit_selected_subgroup_cell();
    void show_tag_context_menu(const QPoint &pos);
    void edit_selected_tag_cell();

private:
    void init_ui(const QString& env_path);
    void load_env(const QString& env_path);
    void update_button_states(bool connected);

    QString m_old_edit_value;

    // --- UI Widgets ---
    QLineEdit *m_db_host;
    QLineEdit *m_db_port;
    QLineEdit *m_db_user;
    QLineEdit *m_db_password;
    QLineEdit *m_db_name;
    
    QPushButton *m_btn_connect;
    QPushButton *m_btn_disconnect;
    QPushButton *m_btn_reset_db;
    
    QLabel *m_stats_label;
    QGroupBox *m_populate_group;
    
    QLineEdit *m_new_group_name_edit;
    QPushButton *m_btn_create_group;
    QPushButton *m_btn_refresh_groups;
    QPushButton *m_btn_remove_group;
    QTableWidget *m_groups_table;
    
    QComboBox *m_new_subgroup_parent_combo;
    QLineEdit *m_new_subgroup_name_edit;
    QPushButton *m_btn_create_subgroup;
    QComboBox *m_existing_subgroups_filter_combo;
    QPushButton *m_btn_refresh_subgroups;
    QPushButton *m_btn_remove_subgroup;
    QTableWidget *m_subgroups_table;
    
    QLineEdit *m_new_tag_name_edit;
    QComboBox *m_new_tag_type_combo;
    QPushButton *m_btn_create_tag;
    QPushButton *m_btn_refresh_tags;
    QPushButton *m_btn_remove_tag;
    QTableWidget *m_tags_table;
};