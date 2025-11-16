#include "tabs/SearchTab.h"

// Assumed paths
#include "tabs/DatabaseTab.h"
#include "src/core/PgvectorImageDatabase.h"
#include "gui/components/OptionalField.h"
#include "gui/components/ImagePreviewWindow.h"
#include "gui/styles/Style.h" // for apply_shadow_effect
#include "src/utils/Definitions.h" // for SUPPORTED_IMG_FORMATS

#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QGridLayout>
#include <QScrollArea>
#include <QGroupBox>
#include <QFormLayout>
#include <QLineEdit>
#include <QPushButton>
#include <QComboBox>
#include <QLabel>
#include <QMessageBox>
#include <QTimer>
#include <QApplication>
#include <QPixmap>
#include <QDesktopServices>
#include <QUrl>
#include <QFileInfo>

// Assuming SUPPORTED_IMG_FORMATS is a QStringList from definitions.h
// extern const QStringList SUPPORTED_IMG_FORMATS;

SearchTab::SearchTab(DatabaseTab* db_tab_ref, bool dropdown, QWidget *parent)
    : BaseTab(parent),
      m_db_tab_ref(db_tab_ref),
      m_dropdown(dropdown),
      m_filename_field(nullptr),
      m_formats_field(nullptr),
      m_input_formats_edit(nullptr)
{
    init_ui();
    update_search_button_state();
}

SearchTab::~SearchTab()
{
    // Close all open preview windows when the tab is destroyed
    clear_results();
}

void SearchTab::init_ui()
{
    QVBoxLayout *layout = new QVBoxLayout(this);
    
    QGroupBox *search_group = new QGroupBox("Search Database");
    QFormLayout *form_layout = new QFormLayout(search_group);
    form_layout->setContentsMargins(10, 20, 10, 10);
    
    group_combo = new QComboBox;
    group_combo->setEditable(true);
    group_combo->setPlaceholderText("e.g., Summer Trip (Optional)");
    form_layout->addRow("Group name:", group_combo);
    
    subgroup_combo = new QComboBox;
    subgroup_combo->setEditable(true);
    subgroup_combo->setPlaceholderText("e.g., Beach Photos (Optional)");
    form_layout->addRow("Subgroup name:", subgroup_combo);
    
    m_filename_edit = new QLineEdit;
    m_filename_edit->setPlaceholderText("e.g., *.png, img_001, etc (Optional)");
    m_filename_field = new OptionalField("Filename pattern", m_filename_edit, false, this);
    form_layout->addRow(m_filename_field);
    
    if (m_dropdown) {
        QVBoxLayout *formats_layout = new QVBoxLayout;
        QHBoxLayout *btn_layout = new QHBoxLayout;
        for (const QString &fmt : SUPPORTED_IMG_FORMATS) {
            QPushButton *btn = new QPushButton(fmt);
            btn->setCheckable(true);
            btn->setStyleSheet("QPushButton:hover { background-color: #3498db; }");
            style::apply_shadow_effect(btn);
            connect(btn, &QPushButton::clicked, this, [this, fmt, btn](){ this->toggle_format(fmt, btn->isChecked()); });
            btn_layout->addWidget(btn);
            m_format_buttons[fmt] = btn;
        }
        formats_layout->addLayout(btn_layout);

        QHBoxLayout *all_btn_layout = new QHBoxLayout;
        m_btn_add_all = new QPushButton("Add All");
        m_btn_add_all->setStyleSheet("background-color: green; color: white;");
        style::apply_shadow_effect(m_btn_add_all);
        connect(m_btn_add_all, &QPushButton::clicked, this, &SearchTab::add_all_formats);
        m_btn_remove_all = new QPushButton("Remove All");
        m_btn_remove_all->setStyleSheet("background-color: red; color: white;");
        style::apply_shadow_effect(m_btn_remove_all);
        connect(m_btn_remove_all, &QPushButton::clicked, this, &SearchTab::remove_all_formats);
        all_btn_layout->addWidget(m_btn_add_all);
        all_btn_layout->addWidget(m_btn_remove_all);
        formats_layout->addLayout(all_btn_layout);

        QWidget *formats_container = new QWidget;
        formats_container->setLayout(formats_layout);
        m_formats_field = new OptionalField("Input formats", formats_container, false, this);
        form_layout->addRow(m_formats_field);
    } else {
        m_input_formats_edit = new QLineEdit;
        m_input_formats_edit->setPlaceholderText("e.g. jpg png gif (optional)");
        form_layout->addRow("Input formats:", m_input_formats_edit);
    }

    m_tags_edit = new QLineEdit;
    m_tags_edit->setPlaceholderText("tag1, tag2, tag3... (comma-separated, optional)");
    form_layout->addRow("Tags:", m_tags_edit);
    layout->addWidget(search_group);
    
    m_search_button = new QPushButton("Search Database");
    m_search_button->setStyleSheet(R"(
        QPushButton {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #667eea, stop:1 #764ba2);
            color: white; font-weight: bold; font-size: 16px;
            padding: 14px; border-radius: 10px; min-height: 44px;
        }
        QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #764ba2, stop:1 #667eea); }
        QPushButton:disabled { background: #4f545c; color: #a0a0a0; }
        QPushButton:pressed { background: #5a67d8; }
    )");
    style::apply_shadow_effect(m_search_button);
    connect(m_search_button, &QPushButton::clicked, this, &SearchTab::perform_search);
    layout->addWidget(m_search_button);
    
    connect(group_combo->lineEdit(), &QLineEdit::returnPressed, m_search_button, &QPushButton::click);
    connect(subgroup_combo->lineEdit(), &QLineEdit::returnPressed, m_search_button, &QPushButton::click);
    connect(m_filename_edit, &QLineEdit::returnPressed, m_search_button, &QPushButton::click);
    connect(m_tags_edit, &QLineEdit::returnPressed, m_search_button, &QPushButton::click);
    if (m_input_formats_edit) {
        connect(m_input_formats_edit, &QLineEdit::returnPressed, m_search_button, &QPushButton::click);
    }
    
    layout->addWidget(new QLabel("Search Results:"));
    m_results_count_label = new QLabel("Not connected to database.");
    m_results_count_label->setStyleSheet("color: #aaa; font-style: italic;");
    layout->addWidget(m_results_count_label);
    
    m_results_scroll = new QScrollArea;
    m_results_scroll->setWidgetResizable(true);
    m_results_scroll->setMinimumHeight(300);
    
    m_results_widget = new QWidget;
    m_results_layout = new QGridLayout(m_results_widget);
    m_results_layout->setAlignment(Qt::AlignTop | Qt::AlignHCenter);
    m_results_scroll->setWidget(m_results_widget);
    
    layout->addWidget(m_results_scroll);
}

// --- Format Toggling ---
void SearchTab::toggle_format(const QString& fmt, bool checked)
{
    if (checked) {
        m_selected_formats.insert(fmt);
        m_format_buttons[fmt]->setStyleSheet(R"(
            QPushButton:checked { background-color: #3320b5; color: white; }
            QPushButton:hover { background-color: #00838a; }
        )");
        style::apply_shadow_effect(m_format_buttons[fmt]);
    } else {
        m_selected_formats.remove(fmt);
        m_format_buttons[fmt]->setStyleSheet("QPushButton:hover { background-color: #3498db; }");
        style::apply_shadow_effect(m_format_buttons[fmt]);
    }
}

void SearchTab::add_all_formats()
{
    for (auto it = m_format_buttons.begin(); it != m_format_buttons.end(); ++it) {
        it.value()->setChecked(true);
        toggle_format(it.key(), true);
    }
}

void SearchTab::remove_all_formats()
{
    for (auto it = m_format_buttons.begin(); it != m_format_buttons.end(); ++it) {
        it.value()->setChecked(false);
        toggle_format(it.key(), false);
    }
}

// --- Search Logic ---
void SearchTab::update_search_button_state()
{
    bool db_connected = m_db_tab_ref && m_db_tab_ref->db != nullptr;
    m_search_button->setEnabled(db_connected);
    if (!db_connected) {
        m_results_count_label->setText("Not connected to database.");
    } else {
        m_results_count_label->setText("Ready to search.");
    }
}

QStringList SearchTab::get_selected_tags()
{
    return join_list_str(m_tags_edit->text());
}

QStringList SearchTab::get_selected_formats()
{
    QStringList formats;
    if (m_dropdown) {
        if (m_selected_formats.isEmpty()) return QStringList();
        formats = QStringList(m_selected_formats.values());
    } else {
        formats = join_list_str(m_input_formats_edit->text());
    }
    
    for (QString &f : formats) {
        f = f.remove(0, 1); // remove leading '.'
    }
    return formats;
}

void SearchTab::perform_search()
{
    if (!m_db_tab_ref || !m_db_tab_ref->db) {
        QMessageBox::warning(this, "Error", "Please connect to the database first.");
        return;
    }
    auto* db = m_db_tab_ref->db;

    m_search_button->setEnabled(False);
    m_search_button->setText("Searching...");
    QApplication::processEvents();
    
    clear_results();
    
    QString group = group_combo->currentText().trimmed();
    QString subgroup = subgroup_combo->currentText().trimmed();
    QString filename = m_filename_edit->text().trimmed();
    QStringList tags = get_selected_tags();
    QStringList formats = get_selected_formats();
    
    if (group.isEmpty() && subgroup.isEmpty() && filename.isEmpty() && tags.isEmpty() && formats.isEmpty()) {
        m_results_count_label->setText("Please enter at least one search criterion.");
        _reset_search_button();
        return;
    }
    
    try {
        QList<QJsonObject> matching_files = db->search_images(
            group.isEmpty() ? QString() : group,
            subgroup.isEmpty() ? QString() : subgroup,
            tags.isEmpty() ? QStringList() : tags,
            filename.isEmpty() ? QString() : filename,
            formats.isEmpty() ? QStringList() : formats,
            100
        );
        display_results(matching_files);

    } catch (const std::exception& e) {
        QMessageBox::critical(this, "Search Error", "An error occurred during search:\n" + QString(e.what()));
        m_results_count_label->setText(QString("Error: %1").arg(e.what()));
    }
    
    QTimer::singleShot(200, this, &SearchTab::_reset_search_button);
}

void SearchTab::_reset_search_button()
{
    m_search_button->setEnabled(true);
    m_search_button->setText("Search Database");
}

// --- Result Handling ---
void SearchTab::display_results(const QList<QJsonObject>& results)
{
    int count = results.length();
    m_results_count_label->setText(QString("Found %1 matching image(s)").arg(count));
    if (count == 0) return;
    
    int columns = 4;
    for (int i = 0; i < count; ++i) {
        QJsonObject img_data = results[i];
        int row = i / columns;
        int col = i % columns;
        
        QString file_path = img_data.value("file_path").toString();
        
        QWidget *result_container = new QWidget;
        QVBoxLayout *result_layout = new QVBoxLayout(result_container);
        result_layout->setContentsMargins(5, 5, 5, 5);
        
        QLabel *image_label = new QLabel;
        image_label->setFixedSize(150, 150);
        image_label->setAlignment(Qt::AlignCenter);
        image_label->setStyleSheet("border: 1px solid #4f545c; background: #36393f;");

        QPixmap pixmap(file_path);
        if (!pixmap.isNull()) {
            image_label->setPixmap(pixmap.scaled(150, 150, Qt::KeepAspectRatio, Qt::SmoothTransformation));
        } else {
            image_label->setText("Not Found");
        }
        result_layout->addWidget(image_label);
        
        QLabel *filename_label = new QLabel(img_data.value("filename").toString("N/A"));
        filename_label->setWordWrap(true);
        filename_label->setAlignment(Qt::AlignCenter);
        filename_label->setStyleSheet("font-size: 10px;");
        result_layout->addWidget(filename_label);
        
        QHBoxLayout *btn_layout = new QHBoxLayout;
        QPushButton *view_button = new QPushButton("View");
        style::apply_shadow_effect(view_button);
        connect(view_button, &QPushButton::clicked, this, [this, file_path](){ this->open_file_preview(file_path); });
        btn_layout->addWidget(view_button);
        
        QPushButton *folder_button = new QPushButton("Folder");
        style::apply_shadow_effect(folder_button);
        connect(folder_button, &QPushButton::clicked, this, [this, file_path](){ this->open_file_directory(file_path); });
        btn_layout->addWidget(folder_button);
        
        result_layout->addLayout(btn_layout);
        
        m_results_layout->addWidget(result_container, row, col);
        m_result_widgets.append(result_container);
    }
}

void SearchTab::remove_preview_window(ImagePreviewWindow* window_instance)
{
    m_open_preview_windows.removeOne(window_instance);
}

void SearchTab::open_file_preview(const QString& file_path)
{
    if (file_path.isEmpty() || !QFileInfo::exists(file_path) || !QFileInfo(file_path).isFile()) {
        QMessageBox::warning(this, "Invalid Path", "File not found at path:\n" + file_path);
        return;
    }

    for (ImagePreviewWindow* window : m_open_preview_windows) {
        if (window->image_path == file_path) {
            window->activateWindow();
            return;
        }
    }
    
    ImagePreviewWindow *preview = new ImagePreviewWindow(file_path, m_db_tab_ref, this);
    connect(preview, &ImagePreviewWindow::finished, this, [this, preview](){ this->remove_preview_window(preview); });
    preview->show();
    m_open_preview_windows.append(preview);
}

void SearchTab::open_file_directory(const QString& file_path)
{
    if (file_path.isEmpty() || !QFileInfo::exists(file_path)) {
        QMessageBox::warning(this, "Invalid Path", "File not found at path:\n" + file_path);
        return;
    }
    QString directory = QFileInfo(file_path).absolutePath();
    QDesktopServices::openUrl(QUrl::fromLocalFile(directory));
}

void SearchTab::clear_results()
{
    for (QWidget *widget : m_result_widgets) {
        widget->deleteLater();
    }
    m_result_widgets.clear();
    
    for (ImagePreviewWindow *window : m_open_preview_windows) {
        window->close();
    }
    m_open_preview_windows.clear();
}

// --- BaseTab Overrides ---
void SearchTab::browse_files() {}
void SearchTab::browse_directory() {}
void SearchTab::browse_input() {}
void SearchTab::browse_output() {}

QJsonObject SearchTab::collect()
{
    QJsonObject out;
    out["group_name"] = group_combo->currentText().trimmed();
    out["subgroup_name"] = subgroup_combo->currentText().trimmed();
    out["filename_pattern"] = m_filename_edit->text().trimmed();
    
    QStringList formats = get_selected_formats();
    if (!formats.isEmpty()) {
        out["input_formats"] = QJsonArray::fromStringList(formats);
    }
    
    QStringList tags = get_selected_tags();
    if (!tags.isEmpty()) {
        out["tags"] = QJsonArray::fromStringList(tags);
    }
    return out;
}