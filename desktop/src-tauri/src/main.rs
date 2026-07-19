// Windows release builds must not open a console window.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    dax_desktop_lib::run()
}
