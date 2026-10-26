use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::process::Command;

#[derive(Serialize, Deserialize)]
pub struct SettingsData {
    pub theme: String,
    pub tab_configurations: HashMap<String, HashMap<String, serde_json::Value>>,
    pub system_preference_profiles: HashMap<String, serde_json::Value>,
    pub active_tab_configs: HashMap<String, String>,
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

sys.path.insert(0, '../../middleware/src')
try:
    from core.vault_manager import VaultManager
    import constants as udef

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

sys.path.insert(0, '../../middleware/src')
try:
    from core.vault_manager import VaultManager
    import constants as udef

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

sys.path.insert(0, '../../middleware/src')
try:
    from core.vault_manager import VaultManager
    import constants as udef

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
