"""
Deep Windows System Integration for VISION:
Package management via Winget, Windows Services via Service Controller / PowerShell,
Event Logs via Wevtutil / PowerShell, Startup Apps via Windows Registry,
Process execution, and Dev Environment diagnostics.
"""

import logging
import os
import shutil
import subprocess
import winreg
from typing import Literal, Optional
from livekit.agents import function_tool

logger = logging.getLogger(__name__)

def _run_cmd(argv: list[str], timeout: int = 30) -> subprocess.CompletedProcess:
    """Executes a command without shell injection."""
    return subprocess.run(argv, shell=False, capture_output=True, text=True, timeout=timeout)

def _run_powershell(script: str, timeout: int = 30) -> subprocess.CompletedProcess:
    """Executes a PowerShell script snippet safely."""
    cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script]
    return subprocess.run(cmd, shell=False, capture_output=True, text=True, timeout=timeout)

# ══════════════════════════════════════════════════════════
#  Windows Package Management (Winget)
# ══════════════════════════════════════════════════════════

@function_tool
async def search_package(query: str) -> str:
    """
    Searches available software packages on Windows using Winget.

    Args:
        query: Software name or keyword to search for (e.g. "vscode", "git", "python", "vlc").
    """
    if not shutil.which("winget"):
        return "Winget package manager is not available on this Windows system."

    try:
        res = _run_cmd(["winget", "search", query, "--accept-source-agreements"], timeout=25)
        output = (res.stdout or res.stderr or "").strip()
        if not output or "No package found" in output:
            return f"No Windows packages found matching '{query}'."
        
        lines = output.splitlines()
        # Cap output to top 15 results
        return f"Winget Search Results for '{query}':\n" + "\n".join(lines[:20])
    except Exception as e:
        return f"Package search failed: {e}"

@function_tool
async def install_package(package_name: str, confirm: bool = False) -> str:
    """
    Installs a software package on Windows using Winget.

    Args:
        package_name: Package ID or exact name to install.
        confirm: Must be set to True — installation will not proceed without confirmation.
    """
    if not confirm:
        return f"'{package_name}' was NOT installed. Please confirm with the user first, then call again with confirm=True."

    if not shutil.which("winget"):
        return "Winget package manager is not available on this Windows system."

    try:
        res = _run_cmd(
            ["winget", "install", "--id", package_name, "-e", "--accept-package-agreements", "--accept-source-agreements", "--silent"],
            timeout=300
        )
        if res.returncode == 0 or "Successfully installed" in res.stdout:
            return f"Package '{package_name}' installed successfully via Winget."
        
        # Try fallback without exact ID match
        res_fallback = _run_cmd(
            ["winget", "install", package_name, "--accept-package-agreements", "--accept-source-agreements", "--silent"],
            timeout=300
        )
        if res_fallback.returncode == 0:
            return f"Package '{package_name}' installed successfully via Winget."

        return f"Installation failed (exit code {res.returncode}):\n{(res.stdout or res.stderr)[:400]}"
    except subprocess.TimeoutExpired:
        return f"Installation of '{package_name}' timed out after 5 minutes."
    except Exception as e:
        return f"Installation failed: {e}"

@function_tool
async def remove_package(package_name: str, confirm: bool = False) -> str:
    """
    Uninstalls a software package on Windows using Winget.

    Args:
        package_name: Package ID or exact name to remove.
        confirm: Must be set to True.
    """
    if not confirm:
        return f"'{package_name}' was NOT uninstalled. Please call again with confirm=True."

    if not shutil.which("winget"):
        return "Winget package manager is not available on this Windows system."

    try:
        res = _run_cmd(["winget", "uninstall", package_name, "--silent"], timeout=180)
        if res.returncode == 0 or "Successfully uninstalled" in res.stdout:
            return f"Package '{package_name}' uninstalled successfully."
        return f"Uninstallation failed:\n{(res.stdout or res.stderr)[:400]}"
    except Exception as e:
        return f"Uninstallation failed: {e}"

@function_tool
async def check_for_updates() -> str:
    """
    Checks for available Windows software updates using Winget.
    """
    if not shutil.which("winget"):
        return "Winget package manager is not installed."

    try:
        res = _run_cmd(["winget", "upgrade"], timeout=45)
        output = (res.stdout or "").strip()
        if not output or "No installed package found matching input criteria" in output:
            return "All software packages are up to date."
        
        lines = output.splitlines()
        return "Available Windows Software Updates:\n" + "\n".join(lines[:25])
    except Exception as e:
        return f"Check for updates failed: {e}"

@function_tool
async def update_system(confirm: bool = False) -> str:
    """
    Upgrades all installed Winget software packages on Windows.

    Args:
        confirm: Must be set to True.
    """
    if not confirm:
        return "System upgrade requested but confirm=False. Call again with confirm=True to proceed."

    if not shutil.which("winget"):
        return "Winget is not available."

    try:
        res = _run_cmd(
            ["winget", "upgrade", "--all", "--include-unknown", "--accept-package-agreements", "--accept-source-agreements", "--silent"],
            timeout=600
        )
        if res.returncode == 0:
            return "All Windows packages upgraded successfully, sir."
        return f"Upgrade finished with output:\n{(res.stdout or res.stderr)[:500]}"
    except Exception as e:
        return f"System update failed: {e}"

# ══════════════════════════════════════════════════════════
#  Windows Services Management
# ══════════════════════════════════════════════════════════

@function_tool
async def list_services(filter_status: Literal["all", "running", "stopped"] = "running") -> str:
    """
    Lists Windows services filtered by status.

    Args:
        filter_status: "all", "running", or "stopped".
    """
    try:
        status_cmd = ""
        if filter_status == "running":
            status_cmd = "Get-Service | Where-Object {$_.Status -eq 'Running'}"
        elif filter_status == "stopped":
            status_cmd = "Get-Service | Where-Object {$_.Status -eq 'Stopped'}"
        else:
            status_cmd = "Get-Service"

        script = f"{status_cmd} | Select-Object -First 30 Name, DisplayName, Status | Format-Table -AutoSize | Out-String"
        res = _run_powershell(script, timeout=15)
        return res.stdout.strip() or "No matching Windows services found."
    except Exception as e:
        return f"Failed to list services: {e}"

@function_tool
async def get_service_status(service_name: str) -> str:
    """
    Retrieves detailed status for a specific Windows service.

    Args:
        service_name: Name or DisplayName of the service.
    """
    try:
        script = f"Get-Service -Name '{service_name}' -ErrorAction SilentlyContinue | Format-List Name, DisplayName, Status, StartType"
        res = _run_powershell(script, timeout=10)
        output = res.stdout.strip()
        if not output:
            return f"Windows service '{service_name}' was not found."
        return f"Service Status:\n{output}"
    except Exception as e:
        return f"Failed to get status for '{service_name}': {e}"

@function_tool
async def control_service(
    service_name: str,
    action: Literal["start", "stop", "restart"],
    confirm: bool = False,
) -> str:
    """
    Starts, stops, or restarts a Windows service.

    Args:
        service_name: Name of the service.
        action: "start", "stop", or "restart".
        confirm: Must be True for "stop" or "restart".
    """
    if action in ("stop", "restart") and not confirm:
        return f"'{action}' service requires confirm=True."

    try:
        cmd_map = {
            "start": f"Start-Service -Name '{service_name}'",
            "stop": f"Stop-Service -Name '{service_name}' -Force",
            "restart": f"Restart-Service -Name '{service_name}' -Force"
        }
        res = _run_powershell(cmd_map[action], timeout=20)
        if res.returncode == 0:
            return f"Windows service '{service_name}' has been {action}ed."
        return f"Service operation failed: {res.stderr.strip()}"
    except Exception as e:
        return f"Service control failed: {e}"

# ══════════════════════════════════════════════════════════
#  Windows Logs & Event Viewer
# ══════════════════════════════════════════════════════════

@function_tool
async def read_system_logs(log_type: Literal["Application", "System", "Security"] = "System", lines: int = 15) -> str:
    """
    Reads recent entries from the Windows Event Log.

    Args:
        log_type: "Application", "System", or "Security".
        lines: Number of recent log entries to retrieve (default: 15).
    """
    try:
        script = f"Get-WinEvent -LogName '{log_type}' -MaxEvents {min(lines, 50)} | Select-Object TimeCreated, Id, LevelDisplayName, Message | Format-Table -Wrap | Out-String"
        res = _run_powershell(script, timeout=15)
        output = res.stdout.strip()
        if not output:
            return f"No log entries found for log type '{log_type}'."
        return f"Windows Event Log ({log_type}):\n{output[:1500]}"
    except Exception as e:
        return f"Failed to read Windows logs: {e}"

# ══════════════════════════════════════════════════════════
#  Docker Containers (Windows Docker Desktop)
# ══════════════════════════════════════════════════════════

@function_tool
async def list_docker_containers() -> str:
    """
    Lists active Docker containers on Windows.
    """
    if not shutil.which("docker"):
        return "Docker is not installed or not available in PATH on this Windows system."

    try:
        res = _run_cmd(["docker", "ps", "-a", "--format", "table {{.ID}}\t{{.Names}}\t{{.Status}}\t{{.Ports}}"], timeout=15)
        output = res.stdout.strip()
        return output or "No Docker containers found."
    except Exception as e:
        return f"Docker list failed: {e}"

@function_tool
async def docker_container_action(
    container_id_or_name: str,
    action: Literal["start", "stop", "restart", "logs"],
) -> str:
    """
    Manages a Docker container (start, stop, restart, or retrieve logs).

    Args:
        container_id_or_name: Container ID or name.
        action: "start", "stop", "restart", or "logs".
    """
    if not shutil.which("docker"):
        return "Docker is not available."

    try:
        if action == "logs":
            res = _run_cmd(["docker", "logs", "--tail", "30", container_id_or_name], timeout=15)
            return f"Container Logs ({container_id_or_name}):\n{(res.stdout or res.stderr)[:1500]}"
        
        res = _run_cmd(["docker", action, container_id_or_name], timeout=30)
        if res.returncode == 0:
            return f"Container '{container_id_or_name}' {action}ed successfully."
        return f"Container action failed: {res.stderr.strip()}"
    except Exception as e:
        return f"Docker action failed: {e}"

# ══════════════════════════════════════════════════════════
#  Windows Dev Environment Info
# ══════════════════════════════════════════════════════════

@function_tool
async def get_dev_environment_info() -> str:
    """
    Reports installed Windows development tools (Python, Node.js, Git, Docker, VS Code, PowerShell version).
    """
    tools_check = [
        ("Python", ["python", "--version"]),
        ("Node.js", ["node", "--version"]),
        ("npm", ["npm", "--version"]),
        ("Git", ["git", "--version"]),
        ("Docker", ["docker", "--version"]),
        ("VS Code", ["code", "--version"]),
        ("Winget", ["winget", "--version"]),
        ("PowerShell", ["powershell", "$PSVersionTable.PSVersion.ToString()"])
    ]

    report = ["Windows Developer Environment Report:"]
    for name, cmd in tools_check:
        if shutil.which(cmd[0]):
            try:
                res = _run_cmd(cmd, timeout=5) if cmd[0] != "powershell" else _run_powershell(cmd[1], timeout=5)
                ver = (res.stdout or res.stderr or "").strip().splitlines()[0]
                report.append(f"• {name}: {ver}")
            except Exception:
                report.append(f"• {name}: Installed")
        else:
            report.append(f"• {name}: Not Installed")

    return "\n".join(report)

# ══════════════════════════════════════════════════════════
#  Windows Startup Apps (Registry Run Keys)
# ══════════════════════════════════════════════════════════

@function_tool
async def list_startup_apps() -> str:
    """
    Lists applications configured to launch at Windows startup.
    """
    startup_apps = []
    reg_paths = [
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run")
    ]

    for hkey, subkey in reg_paths:
        try:
            with winreg.OpenKey(hkey, subkey, 0, winreg.KEY_READ) as key:
                count = winreg.QueryInfoKey(key)[1]
                for i in range(count):
                    name, val, _ = winreg.EnumValue(key, i)
                    startup_apps.append(f"• {name} -> {val}")
        except Exception as reg_err:
            logger.debug(f"Reading Windows Registry path {subkey} failed: {reg_err}")

    if not startup_apps:
        return "No startup applications found in Windows Registry."

    return "Windows Startup Applications:\n" + "\n".join(startup_apps)

@function_tool
async def set_startup_app_enabled(app_name: str, enabled: bool) -> str:
    """
    Enables or disables an app from launching at Windows startup.

    Args:
        app_name: Name of the application registry entry.
        enabled: True to enable startup, False to remove.
    """
    subkey = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        if enabled:
            # Check if app executable exists
            exe_path = shutil.which(app_name)
            if not exe_path:
                return f"Executable for '{app_name}' not found on PATH."
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, subkey, 0, winreg.KEY_SET_VALUE) as key:
                winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, exe_path)
            return f"'{app_name}' enabled for Windows startup."
        else:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, subkey, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, app_name)
            return f"'{app_name}' removed from Windows startup."
    except FileNotFoundError:
        return f"Startup app '{app_name}' was not found in registry."
    except Exception as e:
        return f"Failed to modify startup app: {e}"

# ══════════════════════════════════════════════════════════
#  Windows File Permissions & Attributes
# ══════════════════════════════════════════════════════════

@function_tool
async def get_file_permissions(filepath: str) -> str:
    """
    Inspects Windows file attributes and read/write access permissions.

    Args:
        filepath: Absolute or relative file/folder path.
    """
    if not os.path.exists(filepath):
        return f"Path '{filepath}' does not exist."

    try:
        st = os.stat(filepath)
        readable = os.access(filepath, os.R_OK)
        writable = os.access(filepath, os.W_OK)
        executable = os.access(filepath, os.X_OK)

        return (
            f"Windows Path: {os.path.abspath(filepath)}\n"
            f"Readable: {readable} | Writable: {writable} | Executable: {executable}\n"
            f"Size: {st.st_size} bytes"
        )
    except Exception as e:
        return f"Failed to get file permissions: {e}"

@function_tool
async def set_file_permissions(filepath: str, mode: str) -> str:
    """
    Sets Windows file read-only or read-write mode.

    Args:
        filepath: Target file or directory path.
        mode: "readonly" or "readwrite".
    """
    if not os.path.exists(filepath):
        return f"Path '{filepath}' does not exist."

    try:
        import stat
        if mode == "readonly":
            os.chmod(filepath, stat.S_IREAD)
            return f"Set '{filepath}' to Read-Only."
        else:
            os.chmod(filepath, stat.S_IREAD | stat.S_IWRITE)
            return f"Set '{filepath}' to Read-Write."
    except Exception as e:
        return f"Failed to set file permissions: {e}"

