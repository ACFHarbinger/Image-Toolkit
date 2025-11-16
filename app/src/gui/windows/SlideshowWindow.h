#pragma once

#include <QWidget>
#include <QStringList>
#include <QPoint>

// Forward declarations
class QListWidget;
class QListWidgetItem;
class QLabel;

class SlideshowQueueWindow : public QWidget
{
    Q_OBJECT

public:
    explicit SlideshowQueueWindow(const QString &monitor_name, 
                                  const QString &monitor_id, 
                                  const QStringList &queue, 
                                  QWidget *parent = nullptr);

signals:
    // Signal: (monitor_id, new_queue_list)
    void queue_reordered(const QString &monitor_id, const QStringList &new_queue_list);

private slots:
    void show_context_menu(const QPoint &pos);
    void move_item_up(QListWidgetItem *item);
    void move_item_down(QListWidgetItem *item);
    void remove_item(QListWidgetItem *item);
    void emit_new_queue_order();

private:
    void populate_list(const QStringList &queue);

    QString m_monitor_name;
    QString m_monitor_id;
    
    QLabel *m_title_label;
    QListWidget *m_list_widget;
};