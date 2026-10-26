use serde::{Deserialize, Serialize};
use std::process::Command;

#[derive(Serialize, Deserialize)]
pub struct AuthResult {
    pub success: bool,
    pub message: Option<String>,
    pub profiles: Option<Vec<String>>,
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

sys.path.insert(0, '../../middleware/src')

result = {{'success': False, 'message': 'Unknown error'}}

try:
    from core.vault_manager import VaultManager
    import constants as udef

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

sys.path.insert(0, '../../middleware/src')
result = {{'success': False, 'message': 'Unknown error'}}

try:
    from core.vault_manager import VaultManager
    import constants as udef

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
