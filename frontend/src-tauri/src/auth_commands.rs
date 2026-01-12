use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::PathBuf;
use std::process::Command;

#[derive(Serialize, Deserialize)]
pub struct AuthResult {
    pub success: bool,
    pub message: Option<String>,
    pub profiles: Option<Vec<String>>,
}

#[derive(Serialize, Deserialize)]
pub struct SettingsData {
    pub theme: String,
    pub tab_configurations: HashMap<String, HashMap<String, serde_json::Value>>,
    pub system_preference_profiles: HashMap<String, serde_json::Value>,
    pub active_tab_configs: HashMap<String, String>,
}

/// Authenticate a user using the Python VaultManager backend
#[tauri::command]
pub fn authenticate_user(account_name: String, password: String) -> Result<AuthResult, String> {
    // Call Python backend for authentication
    // This is a bridge between Tauri and the existing Python VaultManager system

    let output = Command::new("python")
        .arg("-c")
        .arg(format!(
            r#"
import sys
import json
sys.path.insert(0, '../../backend/src')
from core.vault_manager import VaultManager
import utils.definitions as udef

try:
    udef.update_cryptographic_values('{}')
    vm = VaultManager(udef.JAR_FILE)
    vm.load_keystore(udef.KEYSTORE_FILE, '{}')
    vm.get_secret_key(udef.KEY_ALIAS, '{}')
    vm.init_vault(udef.VAULT_FILE)
    
    stored_data = vm.load_account_credentials()
    
    # Verify account name
    if stored_data.get('account_name') != '{}':
        print(json.dumps({{'success': False, 'message': 'Account name mismatch'}}))
        sys.exit(1)
    
    # Verify password (hash comparison)
    stored_hash = stored_data.get('hashed_password')
    stored_salt = stored_data.get('salt')
    
    import hashlib
    password_combined = ('{}' + stored_salt + vm.PEPPER).encode('utf-8')
    verification_hash = hashlib.sha256(password_combined).hexdigest()
    
    if verification_hash == stored_hash:
        profiles = list(stored_data.get('system_preference_profiles', {{}}).keys())
        print(json.dumps({{'success': True, 'profiles': profiles}}))
    else:
        print(json.dumps({{'success': False, 'message': 'Invalid password'}}))
        sys.exit(1)
        
except Exception as e:
    print(json.dumps({{'success': False, 'message': str(e)}}))
    sys.exit(1)
"#,
            account_name, password, password, account_name, password
        ))
        .output()
        .map_err(|e| format!("Failed to execute Python: {}", e))?;

    if output.status.success() {
        let result_str = String::from_utf8_lossy(&output.stdout);
        let result: AuthResult = serde_json::from_str(&result_str)
            .map_err(|e| format!("Failed to parse authentication result: {}", e))?;
        Ok(result)
    } else {
        let error = String::from_utf8_lossy(&output.stderr);
        Err(format!("Authentication failed: {}", error))
    }
}

/// Create a new user account using the Python VaultManager backend
#[tauri::command]
pub fn create_user_account(account_name: String, password: String) -> Result<AuthResult, String> {
    let output = Command::new("python")
        .arg("-c")
        .arg(format!(
            r#"
import sys
import json
sys.path.insert(0, '../../backend/src')
from core.vault_manager import VaultManager
import utils.definitions as udef
import os

try:
    udef.update_cryptographic_values('{}')
    
    # Check if account already exists
    if os.path.exists(udef.KEYSTORE_FILE) or os.path.exists(udef.VAULT_FILE):
        print(json.dumps({{'success': False, 'message': 'Account already exists'}}))
        sys.exit(1)
    
    vm = VaultManager(udef.JAR_FILE)
    vm.load_keystore(udef.KEYSTORE_FILE, '{}')
    vm.create_key_if_missing(udef.KEY_ALIAS, udef.KEYSTORE_FILE, '{}')
    vm.get_secret_key(udef.KEY_ALIAS, '{}')
    vm.init_vault(udef.VAULT_FILE)
    vm.save_account_credentials('{}', '{}')
    
    print(json.dumps({{'success': True}}))
    
except Exception as e:
    print(json.dumps({{'success': False, 'message': str(e)}}))
    sys.exit(1)
"#,
            account_name, password, password, password, account_name, password
        ))
        .output()
        .map_err(|e| format!("Failed to execute Python: {}", e))?;

    if output.status.success() {
        let result_str = String::from_utf8_lossy(&output.stdout);
        let result: AuthResult = serde_json::from_str(&result_str)
            .map_err(|e| format!("Failed to parse result: {}", e))?;
        Ok(result)
    } else {
        let error = String::from_utf8_lossy(&output.stderr);
        Err(format!("Account creation failed: {}", error))
    }
}

/// Load user settings from VaultManager
#[tauri::command]
pub fn load_user_settings(account_name: String) -> Result<SettingsData, String> {
    let output = Command::new("python")
        .arg("-c")
        .arg(format!(
            r#"
import sys
import json
sys.path.insert(0, '../../backend/src')
from core.vault_manager import VaultManager
import utils.definitions as udef

try:
    udef.update_cryptographic_values('{}')
    vm = VaultManager(udef.JAR_FILE)
    # Load without password (assumes already authenticated in session)
    vm.init_vault(udef.VAULT_FILE)
    
    stored_data = vm.load_account_credentials()
    
    settings = {{
        'theme': stored_data.get('theme', 'dark'),
        'tab_configurations': stored_data.get('tab_configurations', {{}}),
        'system_preference_profiles': stored_data.get('system_preference_profiles', {{}}),
        'active_tab_configs': stored_data.get('active_tab_configs', {{}})
    }}
    
    print(json.dumps(settings))
    
except Exception as e:
    print(json.dumps({{'error': str(e)}}))
    sys.exit(1)
"#,
            account_name
        ))
        .output()
        .map_err(|e| format!("Failed to execute Python: {}", e))?;

    if output.status.success() {
        let result_str = String::from_utf8_lossy(&output.stdout);
        let settings: SettingsData = serde_json::from_str(&result_str)
            .map_err(|e| format!("Failed to parse settings: {}", e))?;
        Ok(settings)
    } else {
        let error = String::from_utf8_lossy(&output.stderr);
        Err(format!("Failed to load settings: {}", error))
    }
}

/// Save user settings to VaultManager
#[tauri::command]
pub fn save_user_settings(account_name: String, settings: SettingsData) -> Result<bool, String> {
    let settings_json = serde_json::to_string(&settings)
        .map_err(|e| format!("Failed to serialize settings: {}", e))?;

    let output = Command::new("python")
        .arg("-c")
        .arg(format!(
            r#"
import sys
import json
sys.path.insert(0, '../../backend/src')
from core.vault_manager import VaultManager
import utils.definitions as udef

try:
    udef.update_cryptographic_values('{}')
    vm = VaultManager(udef.JAR_FILE)
    vm.init_vault(udef.VAULT_FILE)
    
    user_data = vm.load_account_credentials()
    settings = json.loads('{}')
    
    user_data.update(settings)
    vm.save_data(json.dumps(user_data))
    
    print(json.dumps({{'success': True}}))
    
except Exception as e:
    print(json.dumps({{'success': False, 'error': str(e)}}))
    sys.exit(1)
"#,
            account_name,
            settings_json.replace("'", "\\'")
        ))
        .output()
        .map_err(|e| format!("Failed to execute Python: {}", e))?;

    if output.status.success() {
        Ok(true)
    } else {
        let error = String::from_utf8_lossy(&output.stderr);
        Err(format!("Failed to save settings: {}", error))
    }
}

/// Update master password
#[tauri::command]
pub fn update_master_password(account_name: String, new_password: String) -> Result<bool, String> {
    let output = Command::new("python")
        .arg("-c")
        .arg(format!(
            r#"
import sys
import json
sys.path.insert(0, '../../backend/src')
from core.vault_manager import VaultManager
import utils.definitions as udef

try:
    udef.update_cryptographic_values('{}')
    vm = VaultManager(udef.JAR_FILE)
    vm.update_account_password('{}', '{}')
    
    print(json.dumps({{'success': True}}))
    
except Exception as e:
    print(json.dumps({{'success': False, 'error': str(e)}}))
    sys.exit(1)
"#,
            account_name, account_name, new_password
        ))
        .output()
        .map_err(|e| format!("Failed to execute Python: {}", e))?;

    if output.status.success() {
        Ok(true)
    } else {
        let error = String::from_utf8_lossy(&output.stderr);
        Err(format!("Failed to update password: {}", error))
    }
}
