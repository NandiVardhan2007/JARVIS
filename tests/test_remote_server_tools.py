"""
Unit and integration tests for Remote Ubuntu Server Autopilot & KPR Parking Watchdog tools.
"""

import pytest
from unittest.mock import MagicMock, patch
from vision.tools.registry import tool_registry
from vision.tools.remote_server_tools import (
    ssh_execute_command,
    check_ubuntu_server_health,
    check_parking_logs,
    clear_parking_logs,
    restart_kpr_print_system,
    open_interactive_ssh_terminal
)


def test_remote_server_tools_registered():
    """Verify all remote server tools are registered in tool_registry."""
    tools = [
        "ssh_execute_command",
        "check_ubuntu_server_health",
        "check_parking_logs",
        "clear_parking_logs",
        "restart_kpr_print_system",
        "open_interactive_ssh_terminal"
    ]
    for t in tools:
        schema = tool_registry._schemas.get(t)
        assert schema is not None, f"Tool '{t}' was not registered in ToolRegistry"


@patch("vision.tools.remote_server_tools._get_ssh_client")
def test_ssh_execute_command_success(mock_get_client):
    """Test successful SSH command execution and output formatting."""
    mock_client = MagicMock()
    mock_stdout = MagicMock()
    mock_stdout.read.return_value = b"Linux ubuntu 6.8.0-generic"
    mock_stdout.channel.recv_exit_status.return_value = 0
    
    mock_stderr = MagicMock()
    mock_stderr.read.return_value = b""

    mock_client.exec_command.return_value = (MagicMock(), mock_stdout, mock_stderr)
    mock_get_client.return_value = mock_client

    res = ssh_execute_command("uname -a", host="100.93.70.63")
    assert "Exit code: 0" in res
    assert "Linux ubuntu 6.8.0-generic" in res
    mock_client.close.assert_called_once()


@patch("vision.tools.remote_server_tools.open_parking_logs_terminal")
@patch("vision.tools.remote_server_tools._get_ssh_client")
def test_check_parking_logs(mock_get_client, mock_open_terminal):
    """Test checking KPR parking logs without opening visible GUI CMD."""
    mock_client = MagicMock()
    mock_stdout = MagicMock()
    mock_stdout.read.return_value = b"2026-08-17 05:25:00 - [INFO] Job #104 Printed ticket successfully."
    mock_stdout.channel.recv_exit_status.return_value = 0
    mock_stderr = MagicMock()
    mock_stderr.read.return_value = b""

    mock_client.exec_command.return_value = (MagicMock(), mock_stdout, mock_stderr)
    mock_get_client.return_value = mock_client

    res = check_parking_logs(lines=20, open_terminal=False)
    assert "Printed ticket successfully" in res
    assert "Exit code: 0" in res


@patch("vision.tools.remote_server_tools._get_ssh_client")
def test_clear_parking_logs(mock_get_client):
    """Test clearing KPR parking logs with backup."""
    mock_client = MagicMock()
    mock_stdout = MagicMock()
    mock_stdout.read.return_value = b"Successfully backed up and cleared /home/nandu/print-server/kpr_print.log. New file size: 0 bytes"
    mock_stdout.channel.recv_exit_status.return_value = 0
    mock_stderr = MagicMock()
    mock_stderr.read.return_value = b""

    mock_client.exec_command.return_value = (MagicMock(), mock_stdout, mock_stderr)
    mock_get_client.return_value = mock_client

    res = clear_parking_logs(backup_first=True)
    assert "Successfully backed up and cleared" in res


@patch("vision.tools.remote_server_tools._get_ssh_client")
def test_restart_kpr_print_system(mock_get_client):
    """Test restarting the KPR print system daemon."""
    mock_client = MagicMock()
    mock_stdout = MagicMock()
    mock_stdout.read.return_value = b"Stopping existing print server processes...\nStarting KPR print server in background...\n12345 print_server_ubuntu.py"
    mock_stdout.channel.recv_exit_status.return_value = 0
    mock_stderr = MagicMock()
    mock_stderr.read.return_value = b""

    mock_client.exec_command.return_value = (MagicMock(), mock_stdout, mock_stderr)
    mock_get_client.return_value = mock_client

    res = restart_kpr_print_system()
    assert "Starting KPR print server" in res
