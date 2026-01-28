"""
Keyboard Shortcuts Module
=========================
JavaScript-based keyboard shortcuts for the Streamlit app.
"""

import streamlit as st
from typing import Callable, Optional


# Keyboard shortcut definitions
SHORTCUTS = {
    "Ctrl+O": ("Open file", "open_file"),
    "Space": ("Play/Pause", "play_pause"),
    "Ctrl+L": ("Toggle library", "toggle_library"),
    "Ctrl+E": ("Export", "export"),
    "Escape": ("Cancel", "cancel"),
}


def inject_keyboard_handler():
    """
    Inject JavaScript keyboard event handler into the page.
    Uses st.components to add a hidden listener.
    """
    # Generate JavaScript for keyboard handling
    js_code = """
    <script>
    (function() {
        // Prevent duplicate listeners
        if (window.audiobookShortcutsActive) return;
        window.audiobookShortcutsActive = true;
        
        document.addEventListener('keydown', function(e) {
            // Skip if typing in an input field
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
                return;
            }
            
            let action = null;
            
            // Ctrl+O - Open file
            if (e.ctrlKey && e.key === 'o') {
                e.preventDefault();
                action = 'open_file';
            }
            // Space - Play/Pause
            else if (e.code === 'Space' && !e.ctrlKey && !e.altKey) {
                e.preventDefault();
                action = 'play_pause';
            }
            // Ctrl+L - Toggle library
            else if (e.ctrlKey && e.key === 'l') {
                e.preventDefault();
                action = 'toggle_library';
            }
            // Ctrl+E - Export
            else if (e.ctrlKey && e.key === 'e') {
                e.preventDefault();
                action = 'export';
            }
            // Escape - Cancel
            else if (e.key === 'Escape') {
                action = 'cancel';
            }
            
            if (action) {
                // Store action in hidden element for Streamlit to read
                const actionEl = document.getElementById('keyboard-action');
                if (actionEl) {
                    actionEl.value = action;
                    actionEl.dispatchEvent(new Event('input', { bubbles: true }));
                }
                
                // Also dispatch custom event
                window.dispatchEvent(new CustomEvent('audiobook-shortcut', { 
                    detail: { action: action } 
                }));
            }
        });
        
        console.log('Audiobook keyboard shortcuts activated');
    })();
    </script>
    
    <!-- Hidden input for Streamlit to read keyboard actions -->
    <style>
        #keyboard-action-container {
            position: absolute;
            top: -9999px;
            left: -9999px;
        }
    </style>
    <div id="keyboard-action-container">
        <input type="hidden" id="keyboard-action" value="">
    </div>
    """
    
    st.markdown(js_code, unsafe_allow_html=True)


def render_shortcut_hints():
    """Render keyboard shortcut hints in the UI."""
    st.markdown("### [ shortcuts ]")
    
    hints = [
        ("`Ctrl+O`", "open file"),
        ("`Space`", "play/pause"),
        ("`Ctrl+L`", "library"),
        ("`Ctrl+E`", "export"),
        ("`Esc`", "cancel"),
    ]
    
    for key, action in hints:
        st.markdown(f"{key} — {action}")


def render_shortcut_bar():
    """Render a compact shortcut bar at the bottom of the screen."""
    shortcuts_html = """
    <div style="
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        background: #0A0A0A;
        border-top: 1px solid #1A1A1A;
        padding: 8px 16px;
        font-family: monospace;
        font-size: 11px;
        color: #555555;
        display: flex;
        justify-content: center;
        gap: 24px;
        z-index: 1000;
    ">
        <span><kbd style="color: #FFB000;">Ctrl+O</kbd> open</span>
        <span><kbd style="color: #FFB000;">Space</kbd> play/pause</span>
        <span><kbd style="color: #FFB000;">Ctrl+L</kbd> library</span>
        <span><kbd style="color: #FFB000;">Ctrl+E</kbd> export</span>
        <span><kbd style="color: #FFB000;">Esc</kbd> cancel</span>
    </div>
    """
    st.markdown(shortcuts_html, unsafe_allow_html=True)


def handle_keyboard_action(action: str):
    """
    Handle a keyboard shortcut action.
    Updates session state based on the action.
    
    Args:
        action: The action identifier (e.g., 'play_pause', 'cancel')
    """
    if action == "open_file":
        # Trigger file upload dialog
        # Note: Can't programmatically open file dialog in browser
        st.session_state.view = "upload"
        
    elif action == "play_pause":
        if st.session_state.get("status") == "playing":
            st.session_state.status = "paused"
        else:
            st.session_state.status = "playing"
            
    elif action == "toggle_library":
        if st.session_state.get("view") == "library":
            st.session_state.view = "main"
        else:
            st.session_state.view = "library"
            
    elif action == "export":
        st.session_state.status = "exporting"
        
    elif action == "cancel":
        # Import here to avoid circular dependency
        from modules.ui.progress import request_cancellation
        request_cancellation()
        st.session_state.status = "idle"


def init_keyboard_shortcuts():
    """
    Initialize keyboard shortcuts for the app.
    Call this once in the main app file.
    """
    inject_keyboard_handler()
    
    # Initialize keyboard action state
    if "pending_keyboard_action" not in st.session_state:
        st.session_state.pending_keyboard_action = None


def process_keyboard_actions():
    """
    Process any pending keyboard actions.
    Call this in the main app loop after init.
    """
    action = st.session_state.get("pending_keyboard_action")
    if action:
        handle_keyboard_action(action)
        st.session_state.pending_keyboard_action = None
        st.rerun()
