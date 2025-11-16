#include "LoginWindow.h"

// Assumed paths to your C++ class and definitions
#include "src/core/JavaVaultManager.h"
#include "src/utils/definitions.h" // For JAR_FILE, KEYSTORE_FILE, etc.

#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QLabel>
#include <QLineEdit>
#include <QPushButton>
#include <QMessageBox>
#include <QCloseEvent>
#include <QCryptographicHash>
#include <QDir>
#include <QFile>
#include <QTextStream>
#include <QJsonDocument>
#include <QJsonObject>

// Assuming definitions.h provides these as static consts or in a namespace
// Using namespace method here for clarity.
using namespace udef; 

LoginWindow::LoginWindow(QWidget *parent)
    : QWidget(parent), 
      m_vault_manager(nullptr), 
      m_is_authenticated(false)
{
    setWindowTitle("Secure Login");
    setFixedSize(400, 300);
    
    init_ui();
    apply_styles();
}

LoginWindow::~LoginWindow()
{
    // Destructor
    // If the window is destroyed but login wasn't successful,
    // we must clean up the vault manager.
    if (m_vault_manager && !m_is_authenticated) {
        m_vault_manager->shutdown();
        delete m_vault_manager;
    }
    // If login *was* successful, the MainWindow now owns the m_vault_manager
    // and this pointer is just a copy, so we don't delete it.
}

void LoginWindow::init_ui()
{
    QVBoxLayout *main_layout = new QVBoxLayout(this);
    main_layout->setSpacing(20);
    main_layout->setAlignment(Qt::AlignCenter);

    // Title Label
    QLabel *title_label = new QLabel("Welcome - Secure Toolkit Access");
    title_label->setObjectName("TitleLabel");
    main_layout->addWidget(title_label, 0, Qt::AlignCenter);

    // Input fields
    m_username_input = new QLineEdit;
    m_username_input->setPlaceholderText("Account Name (e.g., user_id_123)");
    m_username_input->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Fixed);
    main_layout->addWidget(m_username_input);

    m_password_input = new QLineEdit;
    m_password_input->setPlaceholderText("Password");
    m_password_input->setEchoMode(QLineEdit::Password);
    m_password_input->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Fixed);
    main_layout->addWidget(m_password_input);
    
    // Button container
    QHBoxLayout *button_layout = new QHBoxLayout;

    m_create_button = new QPushButton("Create Account");
    connect(m_create_button, &QPushButton::clicked, this, &LoginWindow::create_account);
    button_layout->addWidget(m_create_button);

    m_login_button = new QPushButton("Login");
    m_login_button->setObjectName("LoginButton");
    connect(m_login_button, &QPushButton::clicked, this, &LoginWindow::attempt_login);
    m_login_button->setDefault(true);
    button_layout->addWidget(m_login_button);

    main_layout->addLayout(button_layout);
}

void LoginWindow::apply_styles()
{
    const char* qss = R"(
        QWidget {
            background-color: #2d2d30;
            color: #ffffff;
            font-family: Arial;
        }
        #TitleLabel {
            font-size: 16pt;
            font-weight: bold;
            color: #00bcd4;
        }
        QLineEdit {
            background-color: #3e3e42;
            border: 1px solid #5f646c;
            padding: 8px;
            border-radius: 5px;
            color: #ffffff;
        }
        QPushButton {
            background-color: #00bcd4;
            border: none;
            padding: 10px 15px;
            border-radius: 5px;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #00e5ff;
        }
    )";
    this->setStyleSheet(qss);
}

bool LoginWindow::get_credentials(QString &username, QString &password)
{
    username = m_username_input->text().trimmed();
    password = m_password_input->text().trimmed();
    
    if (username.isEmpty() || password.isEmpty()) {
        QMessageBox::warning(this, "Input Error", "Please enter both account name and password.");
        return false;
    }
    return true;
}

void LoginWindow::attempt_login()
{
    QString username, raw_password;
    if (!get_credentials(username, raw_password)) {
        return;
    }

    try {
        // 1. Initialize
        m_vault_manager = new JavaVaultManager(JAR_FILE); 
        
        // 2. KeyStore
        m_vault_manager->load_keystore(KEYSTORE_FILE, raw_password);
        
        // 3. Get Key
        m_vault_manager->get_secret_key(KEY_ALIAS, raw_password);
        m_vault_manager->init_vault(VAULT_FILE);
        
        // 4. Load credentials
        QJsonObject stored_data = m_vault_manager->load_account_credentials();
        
        if (stored_data.value("account_name").toString() != username) {
            QMessageBox::critical(this, "Login Failed", "Account name does not match stored account.");
            delete m_vault_manager;
            m_vault_manager = nullptr;
            return;
        }

        QString stored_hash = stored_data.value("hashed_password").toString();
        QString stored_salt = stored_data.value("salt").toString();
        // Assuming PEPPER is a static member
        const QString pepper = JavaVaultManager::PEPPER; 
        
        // 5. Re-hash and verify
        QString password_combined = raw_password + stored_salt + pepper;
        QString verification_hash = QCryptographicHash::hash(
            password_combined.toUtf8(), QCryptographicHash::Sha256).toHex();
        
        if (verification_hash == stored_hash) {
            QMessageBox::information(this, "Success", QString("Login successful for %1.").arg(username));
            m_is_authenticated = true;
            
            load_api_files();
            
            emit login_successful(m_vault_manager);
            this->close();
        } else {
            QMessageBox::critical(this, "Login Failed", "Invalid password.");
            delete m_vault_manager;
            m_vault_manager = nullptr;
        }
        
    } catch (const std::exception& e) { // Catch standard C++ exceptions
        QMessageBox::critical(this, "Vault Error", QString("An error occurred during login: %1").arg(e.what()));
        if (m_vault_manager) {
            m_vault_manager->shutdown();
            delete m_vault_manager;
            m_vault_manager = nullptr;
        }
    } catch (...) { // Catch-all for Java exceptions or other non-standard errors
        QMessageBox::critical(this, "Vault Error", "An unknown error occurred during login. Check credentials/files.");
        if (m_vault_manager) {
            m_vault_manager->shutdown();
            delete m_vault_manager;
            m_vault_manager = nullptr;
        }
    }
}

void LoginWindow::create_account()
{
    QString username, raw_password;
    if (!get_credentials(username, raw_password)) {
        return;
    }

    try {
        // 1. Initialize
        m_vault_manager = new JavaVaultManager(JAR_FILE);
        
        // 2. Load
        m_vault_manager->load_keystore(KEYSTORE_FILE, raw_password);
        
        // 3. Create Key
        m_vault_manager->create_key_if_missing(KEY_ALIAS, KEYSTORE_FILE, raw_password);
        
        // 4. Retrieve Key
        m_vault_manager->get_secret_key(KEY_ALIAS, raw_password);
        
        // 5. Initialize vault
        m_vault_manager->init_vault(VAULT_FILE);

        // 6. Save credentials
        m_vault_manager->save_account_credentials(username, raw_password);
        
        QMessageBox::information(this, "Success", QString("Account '%1' created and saved securely.").arg(username));
        m_is_authenticated = true;
        
        load_api_files();
        
        emit login_successful(m_vault_manager);
        this->close();

    } catch (const std::exception& e) {
        QMessageBox::critical(this, "Creation Error", QString("Failed to create account: %1").arg(e.what()));
        if (m_vault_manager) {
            m_vault_manager->shutdown();
            delete m_vault_manager;
            m_vault_manager = nullptr;
        }
    } catch (...) {
        QMessageBox::critical(this, "Creation Error", "An unknown error occurred during account creation.");
        if (m_vault_manager) {
            m_vault_manager->shutdown();
            delete m_vault_manager;
            m_vault_manager = nullptr;
        }
    }
}

void LoginWindow::load_api_files()
{
    if (!m_vault_manager || !m_vault_manager->secret_key) {
        qWarning("Vault manager not ready, cannot load API files.");
        return;
    }

    qInfo("Checking for API files to encrypt/decrypt...");
    
    try {
        // Assuming SecureJsonVault is a nested type
        using SecureJsonVault = JavaVaultManager::SecureJsonVault;
        auto* secret_key = m_vault_manager->secret_key;
        
        QDir api_dir(API_DIR);
        if (!api_dir.exists()) {
            qWarning() << "API directory not found, skipping:" << API_DIR;
            return;
        }

        // --- First, encrypt any unencrypted .json files ---
        QStringList json_files = api_dir.entryList(QStringList() << "*.json", QDir::Files);
        for (const QString &filename : json_files) {
            QString json_file_path = api_dir.filePath(filename);
            QString enc_file_path = json_file_path + ".enc";
            
            if (!QFile::exists(enc_file_path)) {
                qInfo() << "Encrypting new file:" << filename << "->" << filename + ".enc";
                try {
                    QFile file(json_file_path);
                    if (!file.open(QIODevice::ReadOnly | QIODevice::Text)) {
                        throw std::runtime_error("Could not open JSON file for reading.");
                    }
                    QTextStream in(&file);
                    QString json_content = in.readAll();
                    file.close();
                    
                    SecureJsonVault temp_file_vault(secret_key, enc_file_path);
                    temp_file_vault.saveData(json_content);
                    
                } catch (const std::exception& e) {
                    qWarning() << "Failed to encrypt" << filename << ":" << e.what();
                } catch (...) {
                    qWarning() << "Failed to encrypt" << filename << ": Unknown Java exception.";
                }
            }
        }

        // --- Second, decrypt and load all .enc files ---
        QStringList enc_files = api_dir.entryList(QStringList() << "*.enc", QDir::Files);
        for (const QString &filename : enc_files) {
            QString enc_file_path = api_dir.filePath(filename);
            QString key_name = filename;
            key_name.remove(".json.enc");
            key_name.remove(".enc");
            
            try {
                // 1. Create a temp vault instance for this file
                SecureJsonVault temp_file_vault(secret_key, enc_file_path);
                
                // 2. Load and decrypt the data
                // Assuming loadData() returns a QString (or something convertible)
                QString decrypted_json_string = temp_file_vault.loadData();
                
                // 3. Parse the string
                QJsonDocument doc = QJsonDocument::fromJson(decrypted_json_string.toUtf8());
                if (doc.isNull() || !doc.isObject()) {
                    throw std::runtime_error("Decrypted data is not valid JSON.");
                }
                
                // 4. Store it in the vault_manager's map
                m_vault_manager->api_credentials.insert(key_name, doc.object());
                qInfo() << "Successfully decrypted and loaded credentials for:" << key_name;

            } catch (const std::exception& e) {
                qWarning() << "Failed to decrypt or parse" << filename << ":" << e.what();
            } catch (...) {
                qWarning() << "Failed to decrypt or parse" << filename << ": Unknown Java exception.";
            }
        }

    } catch (const std::exception& e) {
        qWarning() << "An error occurred during API file loading:" << e.what();
    } catch (...) {
        qWarning() << "An unknown error occurred during API file loading.";
    }
}


void LoginWindow::closeEvent(QCloseEvent *event)
{
    // If window is closed manually without successful login
    if (m_vault_manager && !m_is_authenticated) {
        m_vault_manager->shutdown();
        delete m_vault_manager;
        m_vault_manager = nullptr;
    }
    QWidget::closeEvent(event);
}