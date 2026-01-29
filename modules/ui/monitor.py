
import psutil
import streamlit as st
import os

class SystemMonitor:
    """Monitors system CPU and Memory usage."""
    
    @staticmethod
    def get_stats():
        """Get current system statistics."""
        # CPU Usage (percentage)
        cpu_percent = psutil.cpu_percent(interval=None)
        
        # Memory Usage
        mem = psutil.virtual_memory()
        ram_used_gb = mem.used / (1024 ** 3)
        ram_total_gb = mem.total / (1024 ** 3)
        ram_percent = mem.percent
        
        # Current Process Memory
        process = psutil.Process(os.getpid())
        app_mem_mb = process.memory_info().rss / (1024 ** 2)
        
        return {
            "cpu": cpu_percent,
            "ram_used": ram_used_gb,
            "ram_total": ram_total_gb,
            "ram_percent": ram_percent,
            "app_mem": app_mem_mb
        }

def render_system_stats():
    """Render system stats in a compact container (sidebar/header)."""
    stats = SystemMonitor.get_stats()
    
    # CSS for compact stats - Retro Style
    st.markdown("""
        <style>
        .monitor-container {
            font-family: 'JetBrains Mono', 'Courier New', monospace;
            font-size: 11px;
            color: #888;
            border-top: 1px solid #333;
            margin-top: 20px;
            padding-top: 10px;
        }
        .stat-row {
            display: flex;
            justify_content: space-between;
            margin-bottom: 4px;
        }
        .stat-label { color: #555; }
        .stat-value { color: #FFB000; }
        .stat-value.high { color: #FF4444; }
        </style>
    """, unsafe_allow_html=True)
    
    # Color coding for high usage
    cpu_cls = "high" if stats["cpu"] > 80 else ""
    ram_cls = "high" if stats["ram_percent"] > 90 else ""
    
    st.markdown(f"""
        <div class="monitor-container">
            <div class="stat-row">
                <span class="stat-label">CPU:</span>
                <span class="stat-value {cpu_cls}">{stats['cpu']:.1f}%</span>
            </div>
            <div class="stat-row">
                <span class="stat-label">SYS RAM:</span>
                <span class="stat-value {ram_cls}">{stats['ram_used']:.1f}/{stats['ram_total']:.0f} GB ({stats['ram_percent']}%)</span>
            </div>
            <div class="stat-row">
                <span class="stat-label">APP MEM:</span>
                <span class="stat-value">{stats['app_mem']:.0f} MB</span>
            </div>
        </div>
    """, unsafe_allow_html=True)
