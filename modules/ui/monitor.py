"""
System Monitor Module
====================
Monitors system performance: CPU, RAM, and process memory usage.
Integrates with Streamlit for real-time system stats display.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class SystemStats:
    """Container for system performance metrics."""

    cpu_percent: float
    ram_used_mb: float
    ram_total_mb: float
    ram_percent: float
    process_memory_mb: Optional[float] = None


class SystemMonitor:
    """
    Monitors system resources using psutil.

    Features:
        - CPU usage percentage
        - RAM usage (used/total)
        - Process-specific memory (RSS)
    """

    def __init__(self):
        """Initialize the system monitor."""
        self._has_psutil = False
        try:
            import psutil

            self._has_psutil = True
            self._psutil = psutil
            self._process = psutil.Process(os.getpid())
        except ImportError:
            self._psutil = None
            self._process = None

    def is_available(self) -> bool:
        """Check if system monitoring is available (psutil installed)."""
        return self._has_psutil

    def get_stats(self) -> SystemStats:
        """
        Get current system statistics.

        Returns:
            SystemStats with current metrics
        """
        if not self._has_psutil or not self._psutil:
            # Return zero stats if psutil not available
            return SystemStats(
                cpu_percent=0.0,
                ram_used_mb=0.0,
                ram_total_mb=0.0,
                ram_percent=0.0,
                process_memory_mb=None,
            )

        try:
            # CPU usage (interval=0 means non-blocking)
            cpu_percent = self._psutil.cpu_percent(interval=0.1)

            # RAM usage
            mem = self._psutil.virtual_memory()
            ram_used_mb = mem.used / 1024 / 1024
            ram_total_mb = mem.total / 1024 / 1024
            ram_percent = mem.percent

            # Process memory (RSS - Resident Set Size)
            process_memory_mb = None
            if self._process:
                proc_mem = self._process.memory_info()
                process_memory_mb = proc_mem.rss / 1024 / 1024

            return SystemStats(
                cpu_percent=cpu_percent,
                ram_used_mb=ram_used_mb,
                ram_total_mb=ram_total_mb,
                ram_percent=ram_percent,
                process_memory_mb=process_memory_mb,
            )
        except Exception:
            # Return zero stats on any error
            return SystemStats(
                cpu_percent=0.0,
                ram_used_mb=0.0,
                ram_total_mb=0.0,
                ram_percent=0.0,
                process_memory_mb=None,
            )


def render_system_stats():
    """
    Render system stats as compact badges/metrics in Streamlit.
    Call this from your Streamlit app to display system monitor.
    """
    import streamlit as st

    monitor = SystemMonitor()

    if not monitor.is_available():
        st.markdown(
            "<small>`psutil` not installed - system monitoring unavailable</small>",
            unsafe_allow_html=True,
        )
        return

    stats = monitor.get_stats()

    # Create compact metric display
    col1, col2, col3 = st.columns(3)

    with col1:
        # CPU with color indicator
        cpu_color = (
            "#00FF00"
            if stats.cpu_percent < 50
            else "#FFA500"
            if stats.cpu_percent < 80
            else "#FF3333"
        )
        st.markdown(
            f"<div style='text-align: center;'>"
            f"<span style='font-size: 10px; color: #666;'>CPU</span><br>"
            f"<span style='font-size: 14px; font-weight: bold; color: {cpu_color};'>{stats.cpu_percent:.1f}%</span>"
            f"</div>",
            unsafe_allow_html=True,
        )

    with col2:
        # RAM usage
        ram_gb = stats.ram_used_mb / 1024
        ram_total_gb = stats.ram_total_mb / 1024
        ram_color = (
            "#00FF00"
            if stats.ram_percent < 50
            else "#FFA500"
            if stats.ram_percent < 80
            else "#FF3333"
        )
        st.markdown(
            f"<div style='text-align: center;'>"
            f"<span style='font-size: 10px; color: #666;'>RAM</span><br>"
            f"<span style='font-size: 14px; font-weight: bold; color: {ram_color};'>{ram_gb:.1f}/{ram_total_gb:.1f}GB</span>"
            f"</div>",
            unsafe_allow_html=True,
        )

    with col3:
        # Process memory
        if stats.process_memory_mb:
            proc_gb = stats.process_memory_mb / 1024
            st.markdown(
                f"<div style='text-align: center;'>"
                f"<span style='font-size: 10px; color: #666;'>PROCESS</span><br>"
                f"<span style='font-size: 14px; font-weight: bold; color: #00CCFF;'>{proc_gb:.2f}GB</span>"
                f"</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f"<div style='text-align: center;'>"
                f"<span style='font-size: 10px; color: #666;'>PROCESS</span><br>"
                f"<span style='font-size: 14px; color: #666;'>--</span>"
                f"</div>",
                unsafe_allow_html=True,
            )


def get_system_stats_dict() -> dict:
    """
    Get system stats as a dictionary for programmatic use.

    Returns:
        Dictionary with cpu_percent, ram_used_mb, ram_total_mb, ram_percent, process_memory_mb
    """
    monitor = SystemMonitor()
    stats = monitor.get_stats()
    return {
        "cpu_percent": stats.cpu_percent,
        "ram_used_mb": stats.ram_used_mb,
        "ram_total_mb": stats.ram_total_mb,
        "ram_percent": stats.ram_percent,
        "process_memory_mb": stats.process_memory_mb,
    }
