#pragma once

#include <QWidget>

// Forward declarations
class JavaVaultManager;
class QLineEdit;
class QPushButton;
class QCloseEvent;

class LoginWindow : public QWidget
{
    Q_OBJECT

public:
    explicit LoginWindow(QWidget *parent = nullptr);
    ~LoginWindow();

signals:
    // Emits the authenticated manager instance on success
    void login_successful(JavaVaultManager* vault_manager);

protected:
    void closeEvent(QCloseEvent *event) override;

private slots:
    void attempt_login();
    void create_account();

private:
    void init_ui();
    void apply_styles();
    bool get_credentials(QString &username, QString &password);
    void load_api_files();

    JavaVaultManager* m_vault_manager;
    bool m_is_authenticated;

    // UI elements
    QLineEdit *m_username_input;
    QLineEdit *m_password_input;
    QPushButton *m_create_button;
    QPushButton *m_login_button;
};