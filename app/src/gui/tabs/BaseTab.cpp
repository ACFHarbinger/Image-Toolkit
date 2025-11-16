#include "tabs/BaseTab.h" // Assumed path
#include <QRegularExpression>

BaseTab::BaseTab(QWidget *parent)
    : QWidget(parent)
{
    // Constructor
}

/**
 * @brief Default implementation for set_config.
 * Tabs that are configurable must override this method.
 * This empty implementation allows tabs that *don't* need
 * configuration to not worry about implementing it.
 */
void BaseTab::set_config(const QJsonObject& config)
{
    // Do nothing by default.
    Q_UNUSED(config);
}

/**
 * @brief Default implementation for collect.
 * @return An empty QJsonObject.
 */
QJsonObject BaseTab::collect()
{
    return QJsonObject();
}

/**
 * @brief Convert a comma/space/semicolon separated string to list of strings.
 */
QStringList BaseTab::join_list_str(const QString &s)
{
    if (s.isEmpty()) {
        return QStringList();
    }
    // Use QRegularExpression to split by commas, spaces, or semicolons
    QStringList parts = s.split(QRegularExpression("[\\s,;]+"), Qt::SkipEmptyParts);
    
    // Trim whitespace from each part (though split should handle most)
    for (QString &part : parts) {
        part = part.trimmed();
    }
    return parts;
}