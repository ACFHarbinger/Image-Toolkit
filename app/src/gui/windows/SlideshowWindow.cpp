#include "SlideshowWindow.h"

// This is the assumed path for your custom widget
#include "components/QueueItemWidget.h" 

#include <QVBoxLayout>
#include <QLabel>
#include <QListWidget>
#include <QListWidgetItem>
#include <QPixmap>
#include <QMenu>
#include <QMessageBox>
#include <QApplication>
#include <QStyle>
#include <QIcon>
#include <QFileInfo> // For getting path name
#include <QAbstractItemModel>

SlideshowQueueWindow::SlideshowQueueWindow(const QString &monitor_name, 
                                           const QString &monitor_id, 
                                           const QStringList &queue, 
                                           QWidget *parent)
    : QWidget(parent, Qt::Window), m_monitor_name(monitor_name), m_monitor_id(monitor_id)
{
    setWindowTitle(QString("Queue for %1").arg(monitor_name));
    setMinimumSize(400, 500);

    QVBoxLayout *layout = new QVBoxLayout(this);

    // Title Label
    m_title_label = new QLabel(QString("Queue: %1 Images (Drag or Right-click to modify)").arg(queue.length()));
    m_title_label->setStyleSheet("font-size: 14px; font-weight: bold; padding: 5px;");
    layout->addWidget(m_title_label);

    // The List Widget
    m_list_widget = new QListWidget;
    m_list_widget->setStyleSheet("QListWidget { border: 1px solid #4f545c; border-radius: 8px; }");

    // Enable Drag and Drop
    m_list_widget->setDragDropMode(QListWidget::InternalMove);
    m_list_widget->setSelectionMode(QListWidget::SingleSelection);
    m_list_widget->setDefaultDropAction(Qt::MoveAction);

    // Enable Context Menu
    m_list_widget->setContextMenuPolicy(Qt::CustomContextMenu);
    connect(m_list_widget, &QListWidget::customContextMenuRequested, this, &SlideshowQueueWindow::show_context_menu);

    // Populate the list
    populate_list(queue);
    layout->addWidget(m_list_widget);

    // Connect the model's signal for when rows are moved
    connect(m_list_widget->model(), &QAbstractItemModel::rowsMoved, this, &SlideshowQueueWindow::emit_new_queue_order);
}

void SlideshowQueueWindow::populate_list(const QStringList &queue)
{
    m_list_widget->clear();

    for (const QString &path : queue)
    {
        QPixmap pixmap(path);
        if (pixmap.isNull()) {
            pixmap = QPixmap(80, 60); // Placeholder
            pixmap.fill(Qt::darkGray);
        }

        // Create the custom widget. 
        // It does NOT get a parent, setItemWidget will manage its lifecycle.
        QueueItemWidget *item_widget = new QueueItemWidget(path, pixmap);

        // Create the list item and add it to the list
        QListWidgetItem *list_item = new QListWidgetItem;
        list_item->setSizeHint(item_widget->sizeHint());
        list_item->setData(Qt::UserRole, path); // Store the path data

        // Add item to list *before* setting the widget
        m_list_widget->addItem(list_item);
        m_list_widget->setItemWidget(list_item, item_widget);
    }
}

void SlideshowQueueWindow::show_context_menu(const QPoint &pos)
{
    QListWidgetItem *item = m_list_widget->itemAt(pos);
    if (!item) {
        return;
    }

    m_list_widget->setCurrentItem(item);
    int current_row = m_list_widget->row(item);

    QMenu menu(this);

    // Define Actions with standard icons
    QIcon up_icon = style()->standardIcon(QStyle::SP_ArrowUp);
    QAction *move_up_action = menu.addAction(up_icon, "Move Up");

    QIcon down_icon = style()->standardIcon(QStyle::SP_ArrowDown);
    QAction *move_down_action = menu.addAction(down_icon, "Move Down");

    menu.addSeparator();

    QIcon remove_icon = style()->standardIcon(QStyle::SP_DialogCancelButton);
    QAction *remove_action = menu.addAction(remove_icon, "Remove from Queue");

    // Connect actions using lambda to pass the item instance
    connect(move_up_action, &QAction::triggered, this, [this, item](){ move_item_up(item); });
    connect(move_down_action, &QAction::triggered, this, [this, item](){ move_item_down(item); });
    connect(remove_action, &QAction::triggered, this, [this, item](){ remove_item(item); });

    // Disable actions based on position
    move_up_action->setEnabled(current_row > 0);
    move_down_action->setEnabled(current_row < m_list_widget->count() - 1);

    menu.exec(m_list_widget->mapToGlobal(pos));
}

void SlideshowQueueWindow::move_item_up(QListWidgetItem *item)
{
    int current_row = m_list_widget->row(item);
    if (current_row > 0)
    {
        // 1. Get the custom widget
        QWidget *widget = m_list_widget->itemWidget(item);
        
        // 2. Take the item out (this detaches the widget)
        QListWidgetItem *taken_item = m_list_widget->takeItem(current_row);
        
        // 3. Re-insert
        int new_row = current_row - 1;
        m_list_widget->insertItem(new_row, taken_item);
        
        // 4. Re-associate the widget
        m_list_widget->setItemWidget(taken_item, widget);
        
        // 5. Re-apply size hint
        taken_item->setSizeHint(widget->sizeHint());
        
        m_list_widget->setCurrentItem(taken_item);
        
        // 6. Emit change (the rowsMoved signal should have handled this, 
        //    but we call it directly to match Python logic)
        emit_new_queue_order();
    }
}

void SlideshowQueueWindow::move_item_down(QListWidgetItem *item)
{
    int current_row = m_list_widget->row(item);
    if (current_row < m_list_widget->count() - 1)
    {
        QWidget *widget = m_list_widget->itemWidget(item);
        QListWidgetItem *taken_item = m_list_widget->takeItem(current_row);
        
        int new_row = current_row + 1;
        m_list_widget->insertItem(new_row, taken_item);
        m_list_widget->setItemWidget(taken_item, widget);
        taken_item->setSizeHint(widget->sizeHint());
        
        m_list_widget->setCurrentItem(taken_item);
        emit_new_queue_order();
    }
}

void SlideshowQueueWindow::remove_item(QListWidgetItem *item)
{
    QString file_name = QFileInfo(item->data(Qt::UserRole).toString()).fileName();
    
    auto reply = QMessageBox::question(this, "Remove Image",
                                     QString("Are you sure you want to remove '%1' from this monitor's queue?").arg(file_name),
                                     QMessageBox::Yes | QMessageBox::No, QMessageBox::No);

    if (reply == QMessageBox::Yes) {
        int current_row = m_list_widget->row(item);
        
        // takeItem() removes it from the list, then we must delete it.
        // Deleting the QListWidgetItem will also delete the associated custom widget.
        delete m_list_widget->takeItem(current_row); 
        
        emit_new_queue_order();
    }
}

void SlideshowQueueWindow::emit_new_queue_order()
{
    QStringList new_queue;
    for (int i = 0; i < m_list_widget->count(); ++i)
    {
        QListWidgetItem *item = m_list_widget->item(i);
        new_queue.append(item->data(Qt::UserRole).toString());
    }

    // Update the title
    if (m_title_label) {
         m_title_label->setText(QString("Queue: %1 Images (Drag or Right-click to modify)").arg(new_queue.length()));
    }

    // Emit the signal
    emit queue_reordered(m_monitor_id, new_queue);
}