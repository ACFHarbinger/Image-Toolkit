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

/// Credentials travel on stdin; vault creation runs off the desktop event loop.
#[tauri::command]
pub async fn create_user_account(
    app: tauri::AppHandle,
    account_name: String,
    password: String,
) -> Result<AuthResult, String> {
    use tauri::Manager;
    let resources = app.path().resource_dir().ok();
    tauri::async_runtime::spawn_blocking(move || create_account_request(account_name, password, resources))
        .await
        .map_err(|error| format!("Account creation worker failed: {error}"))?
}

fn create_account_request(
    account: String,
    password: String,
    resources: Option<std::path::PathBuf>,
) -> Result<AuthResult, String> {
    let value = crate::python_json::run_module(
        "middleware.src.services.auth.session",
        &serde_json::json!({"action": "create", "account": account, "password": password}),
        resources,
    )?;
    serde_json::from_value(value).map_err(|error| format!("Invalid account creation response: {error}"))
}

#[cfg(test)]
mod account_creation_tests {
    #[test]
    fn create_command_reaches_session_validation() {
        // Real subprocess boundary, rejected before any account files are touched.
        let result = super::create_account_request("".into(), "test-password".into(), None).unwrap();
        assert!(!result.success);
        assert_eq!(result.message.as_deref(), Some("account is empty"));
    }
}
