#pragma once

#include "tabs/BaseTab.h"
#include <QSet>
#include <QList>
#include <QJsonObject>

// Forward Declarations
class DatabaseTab;
class OptionalField;
class ImagePreviewWindow;
class QLineEdit;
class QComboBox;
class QPushButton;
class QGridLayout;
class QLabel;

class SearchTab : public BaseTab
{
    Q_OBJECT

public:
    explicit SearchTab(DatabaseTab* db_tab_ref, bool dropdown = true, QWidget *parent = nullptr);
    ~SearchTab();

    // --- Public Members (for DatabaseTab) ---
    QComboBox *group_combo;
    QComboBox *subgroup_combo;

    // --- BaseTab Overrides ---
    void browse_files() override;
    void browse_directory() override;
    void browse_input() override;
    void browse_output() override;
    QJsonObject collect() override;
    // set_config(const QJsonObject& config) override; // <-- Uncomment and implement if this tab is configurable

public slots:
    void update_search_button_state();

private slots:
    // --- Format Toggling ---
    void toggle_format(const QString& fmt, bool checked);
    void add_all_formats();
    void remove_all_formats();

    // --- Search Logic ---
    void perform_search();
    void _reset_search_button();

    // --- Result Handling ---
    void open_file_preview(const QString& file_path);
    void open_file_directory(const QString& file_path);
    void remove_preview_window(ImagePreviewWindow* window_instance);
    void clear_results();

private:
    void init_ui();
    QStringList get_selected_tags();
    QStringList get_selected_formats();
    void display_results(const QList<QJsonObject>& results);

    DatabaseTab* m_db_tab_ref;
    bool m_dropdown;

    // --- UI Widgets ---
    QLineEdit* m_filename_edit;
    OptionalField* m_filename_field;
    
    QSet<QString> m_selected_formats;
    QMap<QString, QPushButton*> m_format_buttons;
    QPushButton* m_btn_add_all;
    QPushButton* m_btn_remove_all;
    OptionalField* m_formats_field;
    QLineEdit* m_input_formats_edit; // for non-dropdown
    
    QLineEdit* m_tags_edit;
    QPushButton* m_search_button;
    QLabel* m_results_count_label;
    
    QScrollArea* m_results_scroll;
    QWidget* m_results_widget;
    QGridLayout* m_results_layout;

    QList<QWidget*> m_result_widgets;
    QList<ImagePreviewWindow*> m_open_preview_windows;
};