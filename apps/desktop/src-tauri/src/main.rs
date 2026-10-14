#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    // No plugins: the frontend talks to the API with fetch; no shell/fs/opener access is granted.
    tauri::Builder::default()
        .run(tauri::generate_context!())
        .expect("error while running PIS desktop");
}
