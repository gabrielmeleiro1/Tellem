
import streamlit as st
from datetime import datetime
import collections

# Global buffer for terminal logs (simple in-memory store)
# In a real app with concurrent users, this would need session_state separation
# But since Streamlit runs script top-to-bottom per session, st.session_state is the place.

def init_terminal_state():
    """Initialize terminal state."""
    if "terminal_logs" not in st.session_state:
        st.session_state.terminal_logs = []

def add_terminal_log(message: str, type: str = "info"):
    """
    Add a log message to the terminal buffer.
    
    Args:
        message: Content to display
        type: info, success, warning, error, process
    """
    if "terminal_logs" not in st.session_state:
        st.session_state.terminal_logs = []
        
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    entry = {
        "timestamp": timestamp,
        "message": message,
        "type": type
    }
    st.session_state.terminal_logs.append(entry)
    
    # Keep buffer limited to 100 entries (optimized from 200)
    MAX_LOG_BUFFER = 100
    if len(st.session_state.terminal_logs) > MAX_LOG_BUFFER:
        st.session_state.terminal_logs = st.session_state.terminal_logs[-MAX_LOG_BUFFER:]

def render_terminal_view(_placeholder=None):
    """
    Render the Matrix-style terminal view.
    
    Args:
        _placeholder: Optional container to render into (for live updates)
    """
    init_terminal_state()
    
    # CSS for Matrix Terminal
    css = """
    <style>
        .terminal-window {
            background-color: #000;
            border: 1px solid #333;
            color: #00FF00; /* Classic Matrix Green */
            font-family: 'JetBrains Mono', 'Courier New', monospace;
            font-size: 12px;
            height: 400px;
            overflow-y: auto;
            padding: 10px;
            box-shadow: inset 0 0 20px rgba(0, 50, 0, 0.5);
            display: flex;
            flex-direction: column-reverse; /* Newest at bottom visually if we didn't slice, but we want newest at bottom naturally */
        }
        .log-entry {
            margin-bottom: 2px;
            word-wrap: break-word;
            opacity: 0.9;
        }
        .t-timestamp { color: #444; margin-right: 8px; }
        .t-info { color: #00CC00; }
        .t-process { color: #00FF00; font-weight: bold; text-shadow: 0 0 5px #00FF00; }
        .t-warning { color: #FFA500; }
        .t-error { color: #FF3333; text-shadow: 0 0 5px #FF0000; }
        .t-success { color: #00FFFF; }
        
        .cursor {
            display: inline-block;
            width: 8px;
            height: 14px;
            background-color: #00FF00;
            animation: blink 1s step-end infinite;
            vertical-align: middle;
            margin-left: 5px;
        }
        @keyframes blink { 50% { opacity: 0; } }
    </style>
    """
    
    target = _placeholder if _placeholder else st.container()
    
    with target:
        st.markdown(css, unsafe_allow_html=True)
        
        # Build HTML for logs
        logs_html = '<div class="terminal-window">'
        
        # Show logs (reverse order if we want stick to bottom? Python append adds to end. 
        # HTML flow with scroll usually expects standard order.
        # We want to show the latest at the bottom.
        
        # If we use flex-direction: column, normal order works.
        # But we want to ensure it scrolls to bottom. 
        # For simplicity in pure HTML/CSS without JS scroll, show latest at TOP? 
        # Or just show the last N entries.
        
        for entry in st.session_state.terminal_logs[-50:]:
            ts = entry["timestamp"]
            msg = entry["message"]
            typ = entry["type"]
            css_class = f"t-{typ}"
            
            logs_html += f'<div class="log-entry"><span class="t-timestamp">[{ts}]</span><span class="{css_class}">{msg}</span></div>'
            
        logs_html += '<div class="log-entry"><span class="cursor"></span></div>'
        logs_html += '</div>'
        
        st.markdown(logs_html, unsafe_allow_html=True)
