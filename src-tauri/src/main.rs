// Prevents an extra Windows console from showing up in release builds.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    yt_split_lib::run()
}
