#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::io::{BufRead, BufReader, Write};
use std::net::{TcpListener, TcpStream};
use std::sync::Mutex;
use std::time::{Duration, Instant};

// Refresh token lives in Windows Credential Manager (keyring); the webview never persists it.
const SERVICE: &str = "app.pis.desktop";
const ACCOUNT: &str = "refresh-token";
const WAIT: Duration = Duration::from_secs(180);

#[derive(Default)]
struct Loopback(Mutex<Option<TcpListener>>);

fn entry() -> Result<keyring::Entry, String> {
    keyring::Entry::new(SERVICE, ACCOUNT).map_err(|_| "credential store unavailable".to_string())
}

#[tauri::command]
fn token_save(token: String) -> Result<(), String> {
    entry()?.set_password(&token).map_err(|_| "could not save session".to_string())
}

#[tauri::command]
fn token_load() -> Result<Option<String>, String> {
    match entry()?.get_password() {
        Ok(t) => Ok(Some(t)),
        Err(keyring::Error::NoEntry) => Ok(None),
        Err(_) => Err("could not read session".to_string()),
    }
}

#[tauri::command]
fn token_clear() -> Result<(), String> {
    match entry()?.delete_credential() {
        Ok(()) | Err(keyring::Error::NoEntry) => Ok(()),
        Err(_) => Err("could not clear session".to_string()),
    }
}

/// RFC 8252 loopback redirect: bind 127.0.0.1 on a random port (replaces any earlier pending listener).
#[tauri::command]
fn auth_listen(state: tauri::State<Loopback>) -> Result<u16, String> {
    let l = TcpListener::bind("127.0.0.1:0").map_err(|_| "cannot open sign-in listener".to_string())?;
    l.set_nonblocking(true).map_err(|e| e.to_string())?;
    let port = l.local_addr().map_err(|e| e.to_string())?.port();
    *state.0.lock().unwrap() = Some(l);
    Ok(port)
}

/// Waits for the single redirect request and returns its raw query string (never logged).
#[tauri::command]
async fn auth_wait(state: tauri::State<'_, Loopback>) -> Result<String, String> {
    let l = state.0.lock().unwrap().take().ok_or("no sign-in in progress")?;
    let deadline = Instant::now() + WAIT;
    loop {
        match l.accept() {
            Ok((s, _)) => {
                // Stray requests (favicon, probes) are answered and ignored; only /callback ends the wait.
                if let Some(q) = read_callback(s) {
                    return Ok(q);
                }
            }
            Err(e) if e.kind() == std::io::ErrorKind::WouldBlock => {
                if Instant::now() > deadline {
                    return Err("sign-in timed out".into());
                }
                pause().await;
            }
            Err(_) => return Err("sign-in listener failed".into()),
        }
    }
}

async fn pause() {
    tauri::async_runtime::spawn_blocking(|| std::thread::sleep(Duration::from_millis(100)))
        .await
        .ok();
}

fn read_callback(mut s: TcpStream) -> Option<String> {
    s.set_nonblocking(false).ok();
    s.set_read_timeout(Some(Duration::from_secs(5))).ok();
    let mut line = String::new();
    BufReader::new(&s).read_line(&mut line).ok()?;
    let body = "<html><body>You can close this window and return to NexGauge.</body></html>";
    let _ = write!(
        s,
        "HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{}",
        body.len(),
        body
    );
    // "GET /callback?code=..&state=.. HTTP/1.1"
    let target = line.split_whitespace().nth(1)?;
    let (path, query) = target.split_once('?').unwrap_or((target, ""));
    (path == "/callback").then(|| query.to_string())
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .manage(Loopback::default())
        .invoke_handler(tauri::generate_handler![token_save, token_load, token_clear, auth_listen, auth_wait])
        .run(tauri::generate_context!())
        .expect("error while running NexGauge desktop");
}
