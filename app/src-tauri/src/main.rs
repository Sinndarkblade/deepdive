#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::process::Command;
use std::thread;
use std::time::Duration;

fn main() {
    // Fix NVIDIA + WebKitGTK rendering on Linux
    std::env::set_var("WEBKIT_DISABLE_DMABUF_RENDERER", "1");
    std::env::set_var("WEBKIT_DISABLE_COMPOSITING_MODE", "1");

    // Start the Python backend server
    thread::spawn(|| {
        let project_root = std::env::current_dir()
            .unwrap()
            .parent()
            .unwrap()
            .parent()
            .unwrap()
            .to_path_buf();

        let result = Command::new("python3")
            .arg("-m")
            .arg("server.app")
            .current_dir(&project_root)
            .spawn();

        match result {
            Ok(mut child) => {
                println!("[Tauri] Python server started (PID: {})", child.id());
                let _ = child.wait();
            }
            Err(e) => {
                eprintln!("[Tauri] Failed to start Python server: {}", e);
                eprintln!("[Tauri] Make sure python3 is installed and server/app.py exists");
            }
        }
    });

    // Give the server a moment to start
    thread::sleep(Duration::from_secs(2));

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_opener::init())
        .run(tauri::generate_context!())
        .expect("error while running DeepDive");
}
