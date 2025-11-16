#include "tabs/DatabaseTab.h"

// Assumed paths for dependencies
#include "src/core/PgvectorImageDatabase.h"
#include "tabs/ScanMetadataTab.h"
#include "tabs/SearchTab.h"
#include "gui/styles/Style.h" // For apply_shadow_effect

#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QFormLayout>
#include <QGroupBox>
#include <QLineEdit>
#include <QPushButton>
#include <QLabel>
#include <QTableWidget>
#include <QComboBox>
#include <QScrollArea>
#include <QMessageBox>
#include <QInputDialog>
#include <QHeaderView>
#include <QMenu>
#include <QFile>
#include <QTextStream>

// Constructor
DatabaseTab::DatabaseTab(bool dropdown, const QString& env_path, QWidget *parent)
    : BaseTab(parent),
      db(nullptr),
      scan_tab_ref(nullptr),
      search_tab_ref(nullptr)
{
    init_ui(env_path);
    update_button_states(false);
}

// Destructor
DatabaseTab::~DatabaseTab()
{
    if (db) {
        db->close();
        delete db;
    }
}

// --- UI Initialization ---
void DatabaseTab::init_ui(const QString& env_path)
{
    load_env(env_path); // Load environment variables
    
    QVBoxLayout *main_layout = new QVBoxLayout(this);
    
    // --- PostgreSQL Connection Section ---
    QGroupBox *conn_group = new QGroupBox("PostgreSQL Connection Details");
    QFormLayout *conn_form_layout = new QFormLayout;
    
    m_db_host = new QLineEdit(qgetenv("DB_HOST"));
    m_db_port = new QLineEdit(qgetenv("DB_PORT"));
    m_db_user = new QLineEdit(qgetenv("DB_USER"));
    m_db_password = new QLineEdit(qgetenv("DB_PASSWORD"));
    m_db_password->setEchoMode(QLineEdit::Password);
    m_db_name = new QLineEdit(qgetenv("DB_NAME"));
    
    conn_form_layout->addRow("Host:", m_db_host);
    conn_form_layout->addRow("Port:", m_db_port);
    conn_form_layout->addRow("User:", m_db_user);
    conn_form_layout->addRow("Password:", m_db_password);
    conn_form_layout->addRow("Database Name:", m_db_name);
    
    QVBoxLayout *conn_layout = new QVBoxLayout(conn_group);
    conn_layout->addLayout(conn_form_layout);
    
    QHBoxLayout *button_conn_layout = new QHBoxLayout;
    m_btn_connect = new QPushButton("Connect to PostgreSQL");
    style::apply_shadow_effect(m_btn_connect);
    connect(m_btn_connect, &QPushButton::clicked, this, &DatabaseTab::connect_database);
    button_conn_layout->addWidget(m_btn_connect);
    
    m_btn_disconnect = new QPushButton("Disconnect from PostgreSQL");
    m_btn_disconnect->setStyleSheet("background-color: #f39c12; color: white; padding: 10px;");
    style::apply_shadow_effect(m_btn_disconnect);
    connect(m_btn_disconnect, &QPushButton::clicked, this, &DatabaseTab::disconnect_database);
    button_conn_layout->addWidget(m_btn_disconnect);

    m_btn_reset_db = new QPushButton("⚠️ Reset Database (Drop All Data)");
    m_btn_reset_db->setStyleSheet("background-color: #c0392b; color: white; padding: 10px; font-weight: bold;");
    style::apply_shadow_effect(m_btn_reset_db);
    connect(m_btn_reset_db, &QPushButton::clicked, this, &DatabaseTab::reset_database);
    button_conn_layout->addWidget(m_btn_reset_db);

    conn_layout->addLayout(button_conn_layout);
    main_layout->addWidget(conn_group);
    
    // Statistics display
    m_stats_label = new QLabel("Not connected to database");
    m_stats_label->setStyleSheet("padding: 10px; background-color: #e74c3c; color: white; border-radius: 5px; font-weight: bold;");
    main_layout->addWidget(m_stats_label);
    
    // --- Populate Database Section ---
    m_populate_group = new QGroupBox("Populate Database");
    QVBoxLayout *populate_layout = new QVBoxLayout(m_populate_group);
    
    // --- Create New Group ---
    QGroupBox *create_group_group = new QGroupBox("Create Group(s)");
    QFormLayout *create_group_layout = new QFormLayout(create_group_group);
    m_new_group_name_edit = new QLineEdit;
    m_new_group_name_edit->setPlaceholderText("group1, group2, group3 ... (comma-separated)");
    create_group_layout->addRow("Group Name(s):", m_new_group_name_edit);
    m_btn_create_group = new QPushButton("Create Group(s)");
    style::apply_shadow_effect(m_btn_create_group);
    connect(m_btn_create_group, &QPushButton::clicked, this, &DatabaseTab::create_new_group);
    create_group_layout->addRow(m_btn_create_group);
    connect(m_new_group_name_edit, &QLineEdit::returnPressed, m_btn_create_group, &QPushButton::click);
    populate_layout->addWidget(create_group_group);

    // --- Existing Groups ---
    QGroupBox *existing_groups_group = new QGroupBox("Existing Groups");
    QVBoxLayout *existing_groups_layout = new QVBoxLayout(existing_groups_group);
    QHBoxLayout *groups_btn_layout = new QHBoxLayout;
    m_btn_refresh_groups = new QPushButton("Refresh List");
    style::apply_shadow_effect(m_btn_refresh_groups);
    connect(m_btn_refresh_groups, &QPushButton::clicked, this, &DatabaseTab::refresh_groups_list);
    groups_btn_layout->addWidget(m_btn_refresh_groups);
    m_btn_remove_group = new QPushButton("Remove Selected Group");
    m_btn_remove_group->setStyleSheet("background-color: #f39c12; color: white;");
    style::apply_shadow_effect(m_btn_remove_group);
    connect(m_btn_remove_group, &QPushButton::clicked, this, &DatabaseTab::remove_selected_group);
    groups_btn_layout->addWidget(m_btn_remove_group);
    existing_groups_layout->addLayout(groups_btn_layout);
    m_groups_table = new QTableWidget;
    m_groups_table->setColumnCount(1);
    m_groups_table->setHorizontalHeaderLabels({"Group Name"});
    m_groups_table->horizontalHeader()->setSectionResizeMode(0, QHeaderView::Stretch);
    m_groups_table->setAlternatingRowColors(true);
    m_groups_table->setSelectionBehavior(QAbstractItemView::SelectRows);
    m_groups_table->setSelectionMode(QAbstractItemView::SingleSelection);
    m_groups_table->setStyleSheet(R"(
        QTableWidget { background-color: #36393f; border: 1px solid #4f545c; alternate-background-color: #3b3e44; }
        QHeaderView::section { background-color: #4f545c; color: white; padding: 4px; border: 1px solid #36393f; }
    )");
    m_groups_table->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Expanding);
    m_groups_table->setMinimumHeight(200);
    m_groups_table->setEditTriggers(QAbstractItemView::DoubleClicked);
    m_groups_table->setContextMenuPolicy(Qt::CustomContextMenu);
    connect(m_groups_table, &QTableWidget::customContextMenuRequested, this, &DatabaseTab::show_group_context_menu);
    connect(m_groups_table, &QTableWidget::cellPressed, this, &DatabaseTab::store_old_value);
    connect(m_groups_table, &QTableWidget::itemChanged, this, &DatabaseTab::handle_group_edited);
    existing_groups_layout->addWidget(m_groups_table);
    populate_layout->addWidget(existing_groups_group);
    
    // --- Create New Subgroup ---
    QGroupBox *create_subgroup_group = new QGroupBox("Create Subgroup(s)");
    QFormLayout *create_subgroup_layout = new QFormLayout(create_subgroup_group);
    m_new_subgroup_parent_combo = new QComboBox;
    m_new_subgroup_parent_combo->setPlaceholderText("Select Parent Group...");
    m_new_subgroup_parent_combo->setEditable(true);
    create_subgroup_layout->addRow("Parent Group:", m_new_subgroup_parent_combo);
    m_new_subgroup_name_edit = new QLineEdit;
    m_new_subgroup_name_edit->setPlaceholderText("subgroup1, subgroup2 ... (comma-separated)");
    create_subgroup_layout->addRow("Subgroup Name(s):", m_new_subgroup_name_edit);
    m_btn_create_subgroup = new QPushButton("Create Subgroup(s)");
    style::apply_shadow_effect(m_btn_create_subgroup);
    connect(m_btn_create_subgroup, &QPushButton::clicked, this, &DatabaseTab::create_new_subgroup);
    create_subgroup_layout->addRow(m_btn_create_subgroup);
    connect(m_new_subgroup_name_edit, &QLineEdit::returnPressed, m_btn_create_subgroup, &QPushButton::click);
    populate_layout->addWidget(create_subgroup_group);

    // --- Existing Subgroups ---
    QGroupBox *existing_subgroups_group = new QGroupBox("Existing Subgroups");
    QVBoxLayout *existing_subgroups_layout = new QVBoxLayout(existing_subgroups_group);
    QHBoxLayout *existing_subgroups_filter_layout = new QHBoxLayout;
    existing_subgroups_filter_layout->addWidget(new QLabel("Filter by Group:"));
    m_existing_subgroups_filter_combo = new QComboBox;
    m_existing_subgroups_filter_combo->setPlaceholderText("Select Group to View...");
    existing_subgroups_filter_layout->addWidget(m_existing_subgroups_filter_combo);
    existing_subgroups_layout->addLayout(existing_subgroups_filter_layout);
    connect(m_existing_subgroups_filter_combo, &QComboBox::currentTextChanged, this, &DatabaseTab::refresh_subgroups_list);
    QHBoxLayout *subgroups_btn_layout = new QHBoxLayout;
    m_btn_refresh_subgroups = new QPushButton("Refresh Group Filters");
    style::apply_shadow_effect(m_btn_refresh_subgroups);
    connect(m_btn_refresh_subgroups, &QPushButton::clicked, this, &DatabaseTab::_refresh_all_group_combos);
    subgroups_btn_layout->addWidget(m_btn_refresh_subgroups);
    m_btn_remove_subgroup = new QPushButton("Remove Selected Subgroup");
    m_btn_remove_subgroup->setStyleSheet("background-color: #f39c12; color: white;");
    style::apply_shadow_effect(m_btn_remove_subgroup);
    connect(m_btn_remove_subgroup, &QPushButton::clicked, this, &DatabaseTab::remove_selected_subgroup);
    subgroups_btn_layout->addWidget(m_btn_remove_subgroup);
    existing_subgroups_layout->addLayout(subgroups_btn_layout);
    m_subgroups_table = new QTableWidget;
    m_subgroups_table->setColumnCount(2);
    m_subgroups_table->setHorizontalHeaderLabels({"Subgroup Name", "Parent Group"});
    m_subgroups_table->horizontalHeader()->setSectionResizeMode(0, QHeaderView::Stretch);
    m_subgroups_table->horizontalHeader()->setSectionResizeMode(1, QHeaderView::Stretch);
    m_subgroups_table->setAlternatingRowColors(true);
    m_subgroups_table->setSelectionBehavior(QAbstractItemView::SelectRows);
    m_subgroups_table->setSelectionMode(QAbstractItemView::SingleSelection);
    m_subgroups_table->setStyleSheet(m_groups_table->styleSheet());
    m_subgroups_table->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Expanding);
    m_subgroups_table->setMinimumHeight(200);
    m_subgroups_table->setEditTriggers(QAbstractItemView::DoubleClicked);
    m_subgroups_table->setContextMenuPolicy(Qt::CustomContextMenu);
    connect(m_subgroups_table, &QTableWidget::customContextMenuRequested, this, &DatabaseTab::show_subgroup_context_menu);
    connect(m_subgroups_table, &QTableWidget::cellPressed, this, &DatabaseTab::store_old_value);
    connect(m_subgroups_table, &QTableWidget::itemChanged, this, &DatabaseTab::handle_subgroup_edited);
    existing_subgroups_layout->addWidget(m_subgroups_table);
    populate_layout->addWidget(existing_subgroups_group);
    
    // --- Create New Tag ---
    QGroupBox *create_tag_group = new QGroupBox("Create/Update Tag(s)");
    QFormLayout *create_tag_layout = new QFormLayout(create_tag_group);
    m_new_tag_name_edit = new QLineEdit;
    m_new_tag_name_edit->setPlaceholderText("tag1, tag2, tag3 ... (comma-separated)");
    create_tag_layout->addRow("Tag Name(s):", m_new_tag_name_edit);
    m_new_tag_type_combo = new QComboBox;
    m_new_tag_type_combo->setEditable(true);
    m_new_tag_type_combo->addItems({"", "Artist", "Series", "Character", "General", "Meta"});
    m_new_tag_type_combo->setPlaceholderText("e.g., Artist, Character, General (Optional)");
    create_tag_layout->addRow("Tag Type (applies to all):", m_new_tag_type_combo);
    m_btn_create_tag = new QPushButton("Create/Update Tag(s)");
    style::apply_shadow_effect(m_btn_create_tag);
    connect(m_btn_create_tag, &QPushButton::clicked, this, &DatabaseTab::create_new_tag);
    create_tag_layout->addRow(m_btn_create_tag);
    connect(m_new_tag_name_edit, &QLineEdit::returnPressed, m_btn_create_tag, &QPushButton::click);
    connect(m_new_tag_type_combo->lineEdit(), &QLineEdit::returnPressed, m_btn_create_tag, &QPushButton::click);
    populate_layout->addWidget(create_tag_group);

    // --- Existing Tags ---
    QGroupBox *existing_tags_group = new QGroupBox("Existing Tags");
    QVBoxLayout *existing_tags_layout = new QVBoxLayout(existing_tags_group);
    QHBoxLayout *tags_btn_layout = new QHBoxLayout;
    m_btn_refresh_tags = new QPushButton("Refresh List");
    style::apply_shadow_effect(m_btn_refresh_tags);
    connect(m_btn_refresh_tags, &QPushButton::clicked, this, &DatabaseTab::refresh_tags_list);
    tags_btn_layout->addWidget(m_btn_refresh_tags);
    m_btn_remove_tag = new QPushButton("Remove Selected Tag");
    m_btn_remove_tag->setStyleSheet("background-color: #f39c12; color: white;");
    style::apply_shadow_effect(m_btn_remove_tag);
    connect(m_btn_remove_tag, &QPushButton::clicked, this, &DatabaseTab::remove_selected_tag);
    tags_btn_layout->addWidget(m_btn_remove_tag);
    existing_tags_layout->addLayout(tags_btn_layout);
    m_tags_table = new QTableWidget;
    m_tags_table->setColumnCount(2);
    m_tags_table->setHorizontalHeaderLabels({"Tag Name", "Tag Type"});
    m_tags_table->horizontalHeader()->setSectionResizeMode(0, QHeaderView::Stretch);
    m_tags_table->horizontalHeader()->setSectionResizeMode(1, QHeaderView::Stretch);
    m_tags_table->setAlternatingRowColors(true);
    m_tags_table->setSelectionBehavior(QAbstractItemView::SelectRows);
    m_tags_table->setSelectionMode(QAbstractItemView::SingleSelection);
    m_tags_table->setStyleSheet(m_groups_table->styleSheet());
    m_tags_table->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Expanding);
    m_tags_table->setMinimumHeight(200);
    m_tags_table->setEditTriggers(QAbstractItemView::DoubleClicked);
    m_tags_table->setContextMenuPolicy(Qt::CustomContextMenu);
    connect(m_tags_table, &QTableWidget::customContextMenuRequested, this, &DatabaseTab::show_tag_context_menu);
    connect(m_tags_table, &QTableWidget::cellPressed, this, &DatabaseTab::store_old_value);
    connect(m_tags_table, &QTableWidget::itemChanged, this, &DatabaseTab::handle_tag_edited);
    existing_tags_layout->addWidget(m_tags_table);
    populate_layout->addWidget(existing_tags_group);
    
    QScrollArea *populate_scroll_area = new QScrollArea;
    populate_scroll_area->setWidgetResizable(True);
    populate_scroll_area->setWidget(m_populate_group);
    populate_scroll_area->setStyleSheet("QScrollArea { border: none; }");
    
    main_layout->addWidget(populate_scroll_area);
}

// --- Env Loader ---
void DatabaseTab::load_env(const QString& env_path)
{
    QFile file(env_path);
    if (!file.open(QIODevice::ReadOnly | QIODevice::Text)) {
        qWarning() << "Could not open .env file:" << env_path;
        return;
    }
    
    QTextStream in(&file);
    while (!in.atEnd()) {
        QString line = in.readLine().trimmed();
        if (line.isEmpty() || line.startsWith('#')) {
            continue;
        }
        
        int equalsPos = line.indexOf('=');
        if (equalsPos != -1) {
            QString key = line.left(equalsPos).trimmed();
            QString value = line.mid(equalsPos + 1).trimmed();
            
            // Remove quotes if present
            if (value.startsWith('"') && value.endsWith('"')) {
                value = value.mid(1, value.length() - 2);
            } else if (value.startsWith('\'') && value.endsWith('\'')) {
                value = value.mid(1, value.length() - 2);
            }
            
            qputenv(key.toUtf8(), value.toUtf8());
        }
    }
    file.close();
}

// --- Connection and Statistics ---
void DatabaseTab::connect_database()
{
    try {
        QString db_host = m_db_host->text().trimmed();
        int db_port = m_db_port->text().trimmed().toInt();
        QString db_user = m_db_user->text().trimmed();
        QString db_password = m_db_password->text();
        QString db_name = m_db_name->text().trimmed();
        
        if (db_host.isEmpty() || db_port == 0 || db_user.isEmpty() || db_name.isEmpty()) {
            QMessageBox::warning(this, "Error", "All connection fields are required.");
            return;
        }
        
        if (db) { 
            db->close();
            delete db;
        }
        
        // Assuming PgvectorImageDatabase constructor matches
        db = new PgvectorImageDatabase(db_name, db_user, db_password, db_host, db_port, 128);
        
        update_statistics();
        update_button_states(true);
        _refresh_all_group_combos();
        refresh_subgroup_autocomplete();
        refresh_tags_list();
        refresh_groups_list();
        refresh_subgroups_list();
        
        QMessageBox::information(this, "Success", "Connected to PostgreSQL DB: " + db_name);
    } catch (const std::exception& e) {
        QMessageBox::critical(this, "Error", "Failed to connect to database:\n" + QString(e.what()));
        update_button_states(false);
        m_stats_label->setText("Connection Failed");
        m_stats_label->setStyleSheet("padding: 10px; background-color: #e74c3c; color: white; border-radius: 5px; font-weight: bold;");
        if (db) {
            delete db;
            db = nullptr;
        }
    }
}

void DatabaseTab::disconnect_database()
{
    if (!db) return;
    try {
        db->close();
        delete db;
        db = nullptr;
        update_button_states(false);
        
        m_stats_label->setText("Not connected to database");
        m_stats_label->setStyleSheet("padding: 10px; background-color: #e74c3c; color: white; border-radius: 5px; font-weight: bold;");
        
        m_tags_table->setRowCount(0);
        m_groups_table->setRowCount(0);
        m_subgroups_table->setRowCount(0);
        
        m_new_subgroup_parent_combo->clear();
        m_existing_subgroups_filter_combo->clear();
        
        if (search_tab_ref) {
            // Assuming search_tab_ref has these members
            search_tab_ref->group_combo->clear();
            search_tab_ref->subgroup_combo->clear();
        }
        
        QMessageBox::information(this, "Disconnected", "Successfully disconnected from the database.");
    } catch (const std::exception& e) {
        QMessageBox::critical(this, "Error", "Error during disconnection:\n" + QString(e.what()));
    }
}

void DatabaseTab::reset_database()
{
    if (!db) {
        QMessageBox::warning(this, "Error", "Please connect to a database first");
        return;
    }

    auto confirm1 = QMessageBox::question(
        this, "Confirm Destructive Action",
        "Are you absolutely sure you want to reset the database?\n\n"
        "ALL DATA (images, tags, groups, subgroups) will be PERMANENTLY DELETED.",
        QMessageBox::Yes | QMessageBox::No, QMessageBox::No
    );
    if (confirm1 == QMessageBox::No) return;

    bool ok;
    QString text = QInputDialog::getText(
        this, "Final Confirmation",
        "This is your final warning. This action cannot be undone.\n"
        "This will DROP all tables and recreate the schema.\n\n"
        "Type 'RESET' in the box below to proceed:",
        QLineEdit::Normal, "", &ok
    );
    if (!ok || text.trimmed() != "RESET") {
        QMessageBox::warning(this, "Cancelled", "Input did not match 'RESET'. Database reset was cancelled.");
        return;
    }
        
    try {
        db->reset_database();
        QMessageBox::information(this, "Success", "Database has been reset successfully.");
        
        update_statistics();
        _refresh_all_group_combos();
        refresh_subgroup_autocomplete();
        refresh_tags_list();
        refresh_groups_list();
        refresh_subgroups_list();
    } catch (const std::exception& e) {
        QMessageBox::critical(this, "Error", "Failed to reset database:\n" + QString(e.what()));
    }
}

void DatabaseTab::update_statistics()
{
    if (!db) return;
    try {
        // Assuming get_statistics() returns a QVariantMap or QMap<QString, QVariant>
        auto stats = db->get_statistics();
        QString stats_text = QString(
            "📊 Database Statistics:\n"
            "Images: %1 | Tags: %2 | Groups: %3 | Subgroups: %4"
        ).arg(stats.value("total_images", 0).toInt())
         .arg(stats.value("total_tags", 0).toInt())
         .arg(stats.value("total_groups", 0).toInt())
         .arg(stats.value("total_subgroups", 0).toInt());
        
        m_stats_label->setText(stats_text);
        m_stats_label->setStyleSheet("padding: 10px; background-color: #27ae60; color: white; border-radius: 5px; font-weight: bold;");
    } catch (const std::exception& e) {
        m_stats_label->setText("Error getting statistics: " + QString(e.what()));
        m_stats_label->setStyleSheet("padding: 10px; background-color: #e74c3c; color: white; border-radius: 5px; font-weight: bold;");
    }
}

void DatabaseTab::_refresh_all_group_combos()
{
    if (!db) return;
    try {
        QStringList group_list = db->get_all_groups();
        QStringList items = QStringList() << "" << group_list;
        
        m_new_subgroup_parent_combo->clear();
        m_new_subgroup_parent_combo->addItems(items);
        
        m_existing_subgroups_filter_combo->clear();
        m_existing_subgroups_filter_combo->addItems(items);
        
        if (search_tab_ref) {
            search_tab_ref->group_combo->clear();
            search_tab_ref->group_combo->addItems(items);
            search_tab_ref->group_combo->setCurrentIndex(0);
        }
    } catch (const std::exception& e) {
        qWarning() << "Error refreshing group combos:" << e.what();
        QMessageBox::critical(this, "Error", "Failed to refresh group dropdowns:\n" + QString(e.what()));
    }
}

void DatabaseTab::refresh_subgroup_autocomplete()
{
    if (!db || !search_tab_ref) return;
    try {
        QStringList subgroup_list = db->get_all_subgroups();
        search_tab_ref->subgroup_combo->clear();
        search_tab_ref->subgroup_combo->addItems(QStringList() << "" << subgroup_list);
        search_tab_ref->subgroup_combo->setCurrentIndex(0);
    } catch (const std::exception& e) {
        qWarning() << "Error refreshing subgroup autocomplete:" << e.what();
    }
}

void DatabaseTab::update_button_states(bool connected)
{
    m_btn_connect->setVisible(!connected);
    m_btn_disconnect->setVisible(connected);
    m_btn_reset_db->setVisible(connected);
    
    m_db_host->setEnabled(!connected);
    m_db_port->setEnabled(!connected);
    m_db_user->setEnabled(!connected);
    m_db_password->setEnabled(!connected);
    m_db_name->setEnabled(!connected);

    m_populate_group->setEnabled(connected);
    
    m_btn_remove_group->setEnabled(connected);
    m_btn_remove_subgroup->setEnabled(connected);
    m_btn_remove_tag->setEnabled(connected);
    
    if (scan_tab_ref) {
        scan_tab_ref->update_button_states(connected);
    }
}

// --- Tag and Group Management ---

void DatabaseTab::create_new_group()
{
    if (!db) return;
    QStringList group_names = join_list_str(m_new_group_name_edit->text());
    if (group_names.isEmpty()) {
        QMessageBox::warning(this, "Error", "Group Name(s) cannot be empty.");
        return;
    }
    
    try {
        int count = 0;
        for (const QString &name : group_names) {
            db->add_group(name);
            count++;
        }
        QMessageBox::information(this, "Success", QString("Successfully created %1 group(s).").arg(count));
        m_new_group_name_edit->clear();
        refresh_groups_list(); // This also refreshes combos
        update_statistics();
    } catch (const std::exception& e) {
        QMessageBox::critical(this, "Error", "Failed to create groups:\n" + QString(e.what()));
    }
}

void DatabaseTab::create_new_subgroup()
{
    if (!db) return;
    QString parent_group = m_new_subgroup_parent_combo->currentText().trimmed();
    if (parent_group.isEmpty()) {
        QMessageBox::warning(this, "Error", "You must select or enter a Parent Group.");
        return;
    }
    QStringList subgroup_names = join_list_str(m_new_subgroup_name_edit->text());
    if (subgroup_names.isEmpty()) {
        QMessageBox::warning(this, "Error", "Subgroup Name(s) cannot be empty.");
        return;
    }
    
    try {
        db->add_group(parent_group); // Add parent group if it's new
        
        int count = 0;
        for (const QString &name : subgroup_names) {
            db->add_subgroup(name, parent_group);
            count++;
        }
        
        QMessageBox::information(this, "Success", QString("Successfully created %1 subgroup(s) for '%2'.").arg(count).arg(parent_group));
        m_new_subgroup_name_edit->clear();
        
        _refresh_all_group_combos();
        m_new_subgroup_parent_combo->setCurrentText(parent_group);
        
        if (m_existing_subgroups_filter_combo->currentText() == parent_group) {
            refresh_subgroups_list();
        }
        refresh_subgroup_autocomplete();
        update_statistics();
    } catch (const std::exception& e) {
        QMessageBox::critical(this, "Error", "Failed to create subgroups:\n" + QString(e.what()));
    }
}

void DatabaseTab::create_new_tag()
{
    if (!db) return;
    QStringList tag_names = join_list_str(m_new_tag_name_edit->text());
    QString tag_type = m_new_tag_type_combo->currentText().trimmed();
    if (!tag_type.isEmpty()) {
        tag_type = tag_type.left(1).toUpper() + tag_type.mid(1).toLower();
    }
    
    if (tag_names.isEmpty()) {
        QMessageBox::warning(this, "Error", "Tag Name(s) cannot be empty.");
        return;
    }
    
    try {
        int count = 0;
        for (const QString &name : tag_names) {
            db->add_tag(name, tag_type.isEmpty() ? QString() : tag_type);
            count++;
        }
        QMessageBox::information(this, "Success", QString("Successfully created/updated %1 tag(s).").arg(count));
        m_new_tag_name_edit->clear();
        m_new_tag_type_combo->setCurrentIndex(0);
        refresh_tags_list();
        update_statistics();
    } catch (const std::exception& e) {
        QMessageBox::critical(this, "Error", "Failed to create tags:\n" + QString(e.what()));
    }
}

void DatabaseTab::remove_selected_group()
{
    if (!db) return;
    int current_row = m_groups_table->currentRow();
    if (current_row < 0) {
        QMessageBox::warning(this, "Error", "Please select a group from the list to remove.");
        return;
    }
    QString group_name = m_groups_table->item(current_row, 0)->text();
    
    auto confirm = QMessageBox::question(
        this, "Confirm Delete",
        QString("Are you sure you want to delete the group '%1'?\n\n"
                "WARNING: This will also delete ALL associated subgroups.").arg(group_name),
        QMessageBox::Yes | QMessageBox::No
    );
    
    if (confirm == QMessageBox::Yes) {
        try {
            db->delete_group(group_name);
            refresh_groups_list();
            refresh_subgroups_list();
            refresh_subgroup_autocomplete();
            update_statistics();
            QMessageBox::information(this, "Success", QString("Group '%1' and its subgroups removed.").arg(group_name));
        } catch (const std::exception& e) {
            QMessageBox::critical(this, "Error", "Failed to remove group:\n" + QString(e.what()));
        }
    }
}

void DatabaseTab::remove_selected_subgroup()
{
    if (!db) return;
    int current_row = m_subgroups_table->currentRow();
    if (current_row < 0) {
        QMessageBox::warning(this, "Error", "Please select a subgroup from the list to remove.");
        return;
    }
    QString subgroup_name = m_subgroups_table->item(current_row, 0)->text();
    QString group_name = m_subgroups_table->item(current_row, 1)->text();
    
    auto confirm = QMessageBox::question(
        this, "Confirm Delete",
        QString("Are you sure you want to delete the subgroup '%1' from group '%2'?").arg(subgroup_name, group_name),
        QMessageBox::Yes | QMessageBox::No
    );
    
    if (confirm == QMessageBox::Yes) {
        try {
            db->delete_subgroup(subgroup_name, group_name);
            refresh_subgroups_list();
            refresh_subgroup_autocomplete();
            update_statistics();
            QMessageBox::information(this, "Success", QString("Subgroup '%1' removed.").arg(subgroup_name));
        } catch (const std::exception& e) {
            QMessageBox::critical(this, "Error", "Failed to remove subgroup:\n" + QString(e.what()));
        }
    }
}

void DatabaseTab::remove_selected_tag()
{
    if (!db) return;
    int current_row = m_tags_table->currentRow();
    if (current_row < 0) {
        QMessageBox::warning(this, "Error", "Please select a tag from the list to remove.");
        return;
    }
    QString tag_name = m_tags_table->item(current_row, 0)->text();

    auto confirm = QMessageBox::question(
        this, "Confirm Delete",
        QString("Are you sure you want to delete the tag '%1'?\n\n"
                "WARNING: This will also remove this tag from ALL images that use it.").arg(tag_name),
        QMessageBox::Yes | QMessageBox::No
    );
    
    if (confirm == QMessageBox::Yes) {
        try {
            db->delete_tag(tag_name);
            refresh_tags_list();
            update_statistics();
            QMessageBox::information(this, "Success", QString("Tag '%1' removed.").arg(tag_name));
        } catch (const std::exception& e) {
            QMessageBox::critical(this, "Error", "Failed to remove tag:\n" + QString(e.what()));
        }
    }
}

void DatabaseTab::refresh_groups_list()
{
    if (!db) {
        m_groups_table->setRowCount(0);
        return;
    }
    try {
        QStringList groups = db->get_all_groups();
        m_groups_table->setRowCount(groups.length());
        for (int row = 0; row < groups.length(); ++row) {
            m_groups_table->setItem(row, 0, new QTableWidgetItem(groups[row]));
        }
        _refresh_all_group_combos();
        update_statistics();
    } catch (const std::exception& e) {
        QMessageBox::critical(this, "Error", "Failed to load groups list:\n" + QString(e.what()));
    }
}

void DatabaseTab::refresh_subgroups_list()
{
    if (!db) {
        m_subgroups_table->setRowCount(0);
        return;
    }
    QString parent_group = m_existing_subgroups_filter_combo->currentText();
    if (parent_group.isEmpty()) {
        m_subgroups_table->setRowCount(0);
        return;
    }
    try {
        QStringList subgroups = db->get_subgroups_for_group(parent_group);
        m_subgroups_table->setRowCount(subgroups.length());
        for (int row = 0; row < subgroups.length(); ++row) {
            QTableWidgetItem *name_item = new QTableWidgetItem(subgroups[row]);
            QTableWidgetItem *group_item = new QTableWidgetItem(parent_group);
            group_item->setFlags(group_item->flags() & ~Qt::ItemIsEditable);
            
            m_subgroups_table->setItem(row, 0, name_item);
            m_subgroups_table->setItem(row, 1, group_item);
        }
    } catch (const std::exception& e) {
        QMessageBox::critical(this, "Error", "Failed to load subgroups list:\n" + QString(e.what()));
    }
}

void DatabaseTab::refresh_tags_list()
{
    if (!db) {
        m_tags_table->setRowCount(0);
        return;
    }
    try {
        // Assuming get_all_tags_with_types returns QList<QVariantMap>
        auto tags = db->get_all_tags_with_types();
        m_tags_table->setRowCount(tags.length());
        for (int row = 0; row < tags.length(); ++row) {
            auto tag_data = tags[row].toMap();
            m_tags_table->setItem(row, 0, new QTableWidgetItem(tag_data["name"].toString()));
            m_tags_table->setItem(row, 1, new QTableWidgetItem(tag_data["type"].toString()));
        }
        update_statistics();
    } catch (const std::exception& e) {
        QMessageBox::critical(this, "Error", "Failed to load tags list:\n" + QString(e.what()));
    }
}
    
// --- Context Menu and Edit Handlers ---
void DatabaseTab::store_old_value(int row, int col)
{
    QTableWidget *table = qobject_cast<QTableWidget*>(sender());
    if (!table) return;
    QTableWidgetItem *item = table->item(row, col);
    if (item) {
        m_old_edit_value = item->text();
    }
}

void DatabaseTab::handle_group_edited(QTableWidgetItem *item)
{
    if (!db || m_old_edit_value.isNull()) return;
    QString new_name = item->text().trimmed();
    QString old_name = m_old_edit_value;
    m_old_edit_value.clear();

    if (new_name.isEmpty()) {
        QMessageBox::warning(this, "Error", "Group name cannot be empty.");
        item->setText(old_name);
        return;
    }
    if (new_name == old_name) return;

    try {
        db->rename_group(old_name, new_name);
        refresh_groups_list();
        refresh_subgroups_list();
        update_statistics();
    } catch (const std::exception& e) { // Assuming db throws std::exception on unique violation
        QMessageBox::warning(this, "Error", QString("Failed to rename group (maybe '%1' already exists?):\n%2").arg(new_name, e.what()));
        item->setText(old_name);
    }
}

void DatabaseTab::handle_subgroup_edited(QTableWidgetItem *item)
{
    if (!db || m_old_edit_value.isNull()) return;
    if (item->column() != 0) { // Only allow editing name
        item->setText(m_old_edit_value);
        m_old_edit_value.clear();
        return;
    }

    QString new_name = item->text().trimmed();
    QString old_name = m_old_edit_value;
    m_old_edit_value.clear();
    if (new_name == old_name) return;
    
    QString parent_group = m_subgroups_table->item(item->row(), 1)->text();
    if (new_name.isEmpty()) {
        QMessageBox::warning(this, "Error", "Subgroup name cannot be empty.");
        item->setText(old_name);
        return;
    }
    
    try {
        db->rename_subgroup(old_name, new_name, parent_group);
        refresh_subgroup_autocomplete();
        update_statistics();
    } catch (const std::exception& e) {
        QMessageBox::warning(this, "Error", QString("Failed to rename subgroup:\n%1").arg(e.what()));
        item->setText(old_name);
    }
}
            
void DatabaseTab::handle_tag_edited(QTableWidgetItem *item)
{
    if (!db || m_old_edit_value.isNull()) return;
    QString new_value = item->text().trimmed();
    QString old_value = m_old_edit_value;
    m_old_edit_value.clear();
    if (new_value == old_value) return;

    int row = item->row();
    int col = item->column();

    try {
        if (col == 0) { // Tag Name
            if (new_value.isEmpty()) {
                QMessageBox::warning(this, "Error", "Tag name cannot be empty.");
                item->setText(old_value);
                return;
            }
            db->rename_tag(old_value, new_value);
            if (item->text() != new_value) item->setText(new_value);
            update_statistics();
        } else if (col == 1) { // Tag Type
            QString tag_name = m_tags_table->item(row, 0)->text();
            QString new_type = new_value.isEmpty() ? QString() : (new_value.left(1).toUpper() + new_value.mid(1).toLower());
            db->update_tag_type(tag_name, new_type);
            if (item->text() != new_type) item->setText(new_type);
        }
    } catch (const std::exception& e) {
        QMessageBox::critical(this, "Error", QString("Failed to update tag:\n%1").arg(e.what()));
        item->setText(old_value);
    }
}

void DatabaseTab::show_group_context_menu(const QPoint &pos)
{
    QTableWidgetItem *item = m_groups_table->itemAt(pos);
    if (!item) return;
    m_groups_table->setCurrentItem(item); // Select the row
    QMenu menu;
    QAction *edit_action = menu.addAction("Edit Group");
    QAction *remove_action = menu.addAction("Remove Group");
    QAction *selected_action = menu.exec(m_groups_table->mapToGlobal(pos));
    if (selected_action == edit_action) {
        edit_selected_group_cell();
    } else if (selected_action == remove_action) {
        remove_selected_group();
    }
}

void DatabaseTab::edit_selected_group_cell()
{
    QTableWidgetItem *item = m_groups_table->currentItem();
    if (item) m_groups_table->editItem(item);
}

void DatabaseTab::show_subgroup_context_menu(const QPoint &pos)
{
    QTableWidgetItem *item = m_subgroups_table->itemAt(pos);
    if (!item) return;
    m_subgroups_table->setCurrentItem(item);
    QMenu menu;
    QAction *edit_action = (item->column() == 0) ? menu.addAction("Edit Subgroup") : nullptr;
    QAction *remove_action = menu.addAction("Remove Subgroup");
    QAction *selected_action = menu.exec(m_subgroups_table->mapToGlobal(pos));
    if (selected_action == edit_action) {
        edit_selected_subgroup_cell();
    } else if (selected_action == remove_action) {
        remove_selected_subgroup();
    }
}

void DatabaseTab::edit_selected_subgroup_cell()
{
    int row = m_subgroups_table->currentRow();
    if (row < 0) return;
    QTableWidgetItem *item = m_subgroups_table->item(row, 0);
    if (item) m_subgroups_table->editItem(item);
}

void DatabaseTab::show_tag_context_menu(const QPoint &pos)
{
    QTableWidgetItem *item = m_tags_table->itemAt(pos);
    if (!item) return;
    m_tags_table->setCurrentItem(item);
    QMenu menu;
    QAction *edit_action = menu.addAction("Edit Cell");
    QAction *remove_action = menu.addAction("Remove Tag");
    QAction *selected_action = menu.exec(m_tags_table->mapToGlobal(pos));
    if (selected_action == edit_action) {
        edit_selected_tag_cell();
    } else if (selected_action == remove_action) {
        remove_selected_tag();
    }
}

void DatabaseTab::edit_selected_tag_cell()
{
    QTableWidgetItem *item = m_tags_table->currentItem();
    if (item) m_tags_table->editItem(item);
}
            
// --- BaseTab Overrides ---
void DatabaseTab::browse_files() {}
void DatabaseTab::browse_directory() {}
void DatabaseTab::browse_input() {}
void DatabaseTab::browse_output() {}
QJsonObject DatabaseTab::collect()
{
    QJsonObject out;
    out["db_host"] = m_db_host->text().trimmed();
    out["db_port"] = m_db_port->text().trimmed();
    out["db_user"] = m_db_user->text().trimmed();
    out["db_name"] = m_db_name->text().trimmed();
    return out;
}