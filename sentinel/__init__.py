"""
Sentinel – Standalone background monitoring daemon.

Monitors Docker containers deployed by Vectra, detects crashes,
and triggers a LangGraph-based post-mortem AI workflow to diagnose
root causes and dispatch email notifications.
"""
