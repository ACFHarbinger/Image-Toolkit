use serde::{Deserialize, Serialize};
use std::collections::HashMap;
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

    let python_script = format!(
        r#"
import sys
import json
import hashlib
# Redirect stdout to stderr
_orig_stdout = sys.stdout
sys.stdout = sys.stderr

sys.path.insert(0, '../../backend/src')

result = {{'success': False, 'message': 'Unknown error'}}

try:
    from core.vault_manager import VaultManager
    import utils.definitions as udef

    udef.update_cryptographic_values('{}')
    vm = VaultManager(udef.JAR_FILE)
    vm.load_keystore(udef.KEYSTORE_FILE, '{}')
    vm.get_secret_key(udef.KEY_ALIAS, '{}')
    vm.init_vault(udef.VAULT_FILE)
    
    stored_data = vm.load_account_credentials()
    
    if stored_data.get('account_name') != '{}':
        result = {{'success': False, 'message': 'Account name mismatch'}}
    else:
        # Verify password (hash comparison)
        stored_hash = stored_data.get('hashed_password')
        stored_salt = stored_data.get('salt')
        
        password_combined = ('{}' + stored_salt + vm.PEPPER).encode('utf-8')
        verification_hash = hashlib.sha256(password_combined).hexdigest()
        
        if verification_hash == stored_hash:
            profiles = list(stored_data.get('system_preference_profiles', {{}}).keys())
            result = {{'success': True, 'profiles': profiles}}
        else:
            result = {{'success': False, 'message': 'Invalid password'}}
        
except Exception as e:
    result = {{'success': False, 'message': str(e)}}

sys.stdout = _orig_stdout
print(f"RESULT: {{json.dumps(result)}}")
"#,
        account_name, password, password, account_name, password
    );

    let output = Command::new("python3")
        .arg("-c")
        .arg(&python_script)
        .output()
        .map_err(|e| format!("Failed to execute Python: {}", e))?;

    let stdout = String::from_utf8_lossy(&output.stdout);
    let stderr = String::from_utf8_lossy(&output.stderr);

    if !stderr.is_empty() {
        log::info!("Python stderr: {}", stderr);
    }

    // Find the line starting with RESULT:
    let result_line = stdout
        .lines()
        .find(|line| line.starts_with("RESULT: "))
        .ok_or_else(|| {
            log::error!("No RESULT: marker found in output. Raw output: {}", stdout);
            format!("No authentication result marker found in backend output")
        })?;

    let json_str = &result_line["RESULT: ".len()..];

    serde_json::from_str(json_str).map_err(|e| {
        format!(
            "Failed to parse authentication result: {}. JSON was: {}",
            e, json_str
        )
    })
}

/// Create a new user account using the Python VaultManager backend
#[tauri::command]
pub fn create_user_account(account_name: String, password: String) -> Result<AuthResult, String> {
    let python_script = format!(
        r#"
import sys
import json
import os
# Redirect stdout to stderr
_orig_stdout = sys.stdout
sys.stdout = sys.stderr

sys.path.insert(0, '../../backend/src')
result = {{'success': False, 'message': 'Unknown error'}}

try:
    from core.vault_manager import VaultManager
    import utils.definitions as udef

    udef.update_cryptographic_values('{}')
    
    if os.path.exists(udef.KEYSTORE_FILE) or os.path.exists(udef.VAULT_FILE):
        result = {{'success': False, 'message': 'Account already exists'}}
    else:
        vm = VaultManager(udef.JAR_FILE)
        vm.load_keystore(udef.KEYSTORE_FILE, '{}')
        vm.create_key_if_missing(udef.KEY_ALIAS, udef.KEYSTORE_FILE, '{}')
        vm.get_secret_key(udef.KEY_ALIAS, '{}')
        vm.init_vault(udef.VAULT_FILE)
        vm.save_account_credentials('{}', '{}')
        result = {{'success': True}}
    
except Exception as e:
    result = {{'success': False, 'message': str(e)}}

sys.stdout = _orig_stdout
print(f"RESULT: {{json.dumps(result)}}")
"#,
        account_name, password, password, password, account_name, password
    );

    let output = Command::new("python3")
        .arg("-c")
        .arg(&python_script)
        .output()
        .map_err(|e| format!("Failed to execute Python: {}", e))?;

    let stdout = String::from_utf8_lossy(&output.stdout);
    let stderr = String::from_utf8_lossy(&output.stderr);

    if !stderr.is_empty() {
        log::info!("Python stderr: {}", stderr);
    }

    // Find the line starting with RESULT:
    let result_line = stdout
        .lines()
        .find(|line| line.starts_with("RESULT: "))
        .ok_or_else(|| {
            log::error!("No RESULT: marker found in output. Raw output: {}", stdout);
            format!("No account creation result marker found in backend output")
        })?;

    let json_str = &result_line["RESULT: ".len()..];

    serde_json::from_str(json_str).map_err(|e| {
        format!(
            "Failed to parse account creation result: {}. JSON was: {}",
            e, json_str
        )
    })
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
# Redirect stdout to stderr
_original_stdout = sys.stdout
sys.stdout = sys.stderr

sys.path.insert(0, '../../backend/src')
try:
    from core.vault_manager import VaultManager
    import utils.definitions as udef

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
    
    sys.stdout = _original_stdout
    print(json.dumps(settings))
    
except Exception as e:
    print(str(e))
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
# Redirect stdout to stderr
_original_stdout = sys.stdout
sys.stdout = sys.stderr

sys.path.insert(0, '../../backend/src')
try:
    from core.vault_manager import VaultManager
    import utils.definitions as udef

    udef.update_cryptographic_values('{}')
    vm = VaultManager(udef.JAR_FILE)
    vm.init_vault(udef.VAULT_FILE)
    
    user_data = vm.load_account_credentials()
    settings = json.loads('{}')
    
    user_data.update(settings)
    vm.save_data(json.dumps(user_data))
    
    sys.stdout = _original_stdout
    print(json.dumps({{'success': True}}))
    
except Exception as e:
    print(str(e))
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
# Redirect stdout to stderr
_original_stdout = sys.stdout
sys.stdout = sys.stderr

sys.path.insert(0, '../../backend/src')
try:
    from core.vault_manager import VaultManager
    import utils.definitions as udef

    udef.update_cryptographic_values('{}')
    vm = VaultManager(udef.JAR_FILE)
    vm.update_account_password('{}', '{}')
    
    sys.stdout = _original_stdout
    print(json.dumps({{'success': True}}))
    
except Exception as e:
    print(str(e))
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
