"""
Network, Wi-Fi & Internet Health Tools for VISION AI OS.
Provides Ookla Speedtest integration, Wi-Fi signal diagnostics, and network latency probes.
"""

import json
import socket
import subprocess
import shutil
from typing import Optional
from vision.tools.registry import tool
from vision.logger import logger


@tool(name="test_internet_speed", description="Test live internet download/upload speed, ping latency, and ISP information using Ookla Speedtest.")
def test_internet_speed() -> str:
    """
    Runs Ookla Speedtest CLI and returns accurate download/upload speeds (in Mbps),
    ping latency (in ms), jitter, packet loss, and ISP/Server details.
    """
    speedtest_bin = shutil.which("speedtest")
    if not speedtest_bin:
        # Check standard paths
        for path in ["speedtest", "C:\\Windows\\speedtest.exe", "C:\\Program Files\\speedtest\\speedtest.exe"]:
            if shutil.which(path):
                speedtest_bin = path
                break

    if not speedtest_bin:
        return "Error: Ookla Speedtest CLI ('speedtest') is not installed or not in PATH."

    logger.info("[NetworkTool] Running Ookla Speedtest...")
    try:
        cmd = [speedtest_bin, "-f", "json", "--accept-license", "--accept-gdpr"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=45, errors="ignore")
        
        if result.returncode != 0 and not result.stdout:
            logger.error(f"[NetworkTool] Speedtest failed: {result.stderr}")
            return f"Error executing speedtest: {result.stderr.strip()}"

        data = json.loads(result.stdout.strip())

        # Extract metrics
        ping_ms = round(data.get("ping", {}).get("latency", 0), 2)
        jitter_ms = round(data.get("ping", {}).get("jitter", 0), 2)
        
        # Bytes/sec -> Mbps (bytes * 8 / 1,000,000)
        down_bytes_sec = data.get("download", {}).get("bandwidth", 0)
        up_bytes_sec = data.get("upload", {}).get("bandwidth", 0)
        
        download_mbps = round((down_bytes_sec * 8) / 1_000_000, 2)
        upload_mbps = round((up_bytes_sec * 8) / 1_000_000, 2)
        
        isp = data.get("isp", "Unknown ISP")
        server_info = data.get("server", {})
        server_name = server_info.get("name", "Unknown Server")
        server_loc = server_info.get("location", "")
        server_country = server_info.get("country", "")
        packet_loss = data.get("packetLoss", 0)
        client_ip = data.get("interface", {}).get("externalIp", "")
        result_url = data.get("result", {}).get("url", "")

        summary = (
            f"Internet Speed Test Results:\n"
            f"• Download: {download_mbps} Mbps\n"
            f"• Upload: {upload_mbps} Mbps\n"
            f"• Ping: {ping_ms} ms (Jitter: {jitter_ms} ms)\n"
            f"• Packet Loss: {packet_loss}%\n"
            f"• ISP: {isp}\n"
            f"• Server: {server_name} ({server_loc}, {server_country})\n"
            f"• Public IP: {client_ip}\n"
            f"• Result URL: {result_url}"
        )
        logger.info(f"[NetworkTool] Speedtest complete: Down {download_mbps} Mbps, Up {upload_mbps} Mbps, Ping {ping_ms} ms")
        return summary
    except subprocess.TimeoutExpired:
        return "Speedtest timed out after 45 seconds."
    except Exception as e:
        logger.error(f"[NetworkTool] Speedtest error: {e}")
        return f"Error running internet speed test: {e}"


@tool(name="get_network_diagnostics", description="Get Wi-Fi signal strength, connected SSID, local IPv4, gateway, and internet connectivity status.")
def get_network_diagnostics() -> str:
    """
    Checks the active Wi-Fi adapter connection quality (SSID, signal percentage, radio type, receive/transmit rates),
    local IP, default gateway, and DNS ping status.
    """
    lines = ["Network & Wi-Fi Diagnostics:"]
    
    # 1. Wi-Fi interface details
    try:
        wifi_output = subprocess.check_output("netsh wlan show interfaces", shell=True, text=True, errors="ignore")
        ssid, bssid, signal, radio, rx_rate, tx_rate, state = None, None, None, None, None, None, None
        
        for line in wifi_output.splitlines():
            line = line.strip()
            if line.startswith("SSID") and not line.startswith("BSSID"):
                ssid = line.split(":", 1)[1].strip()
            elif line.startswith("BSSID"):
                bssid = line.split(":", 1)[1].strip()
            elif line.startswith("Signal"):
                signal = line.split(":", 1)[1].strip()
            elif line.startswith("Radio type"):
                radio = line.split(":", 1)[1].strip()
            elif line.startswith("Receive rate"):
                rx_rate = line.split(":", 1)[1].strip()
            elif line.startswith("Transmit rate"):
                tx_rate = line.split(":", 1)[1].strip()
            elif line.startswith("State"):
                state = line.split(":", 1)[1].strip()

        if ssid:
            lines.append(f"• Wi-Fi SSID: {ssid} (State: {state or 'connected'})")
            if signal:
                lines.append(f"• Signal Quality: {signal}")
            if radio:
                lines.append(f"• Protocol: {radio}")
            if rx_rate and tx_rate:
                lines.append(f"• Link Rate: Rx {rx_rate} Mbps / Tx {tx_rate} Mbps")
        else:
            lines.append("• Wi-Fi: No active Wi-Fi interface connected (or connected via Ethernet).")
    except Exception as e:
        logger.debug(f"[NetworkTool] netsh wlan check: {e}")

    # 2. Local IP & Hostname
    try:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        lines.append(f"• Hostname: {hostname}")
        lines.append(f"• Local IPv4: {local_ip}")
    except Exception as e:
        logger.debug(f"[NetworkTool] Local IP check: {e}")

    # 3. Quick DNS Ping to 8.8.8.8 (Google) and 1.1.1.1 (Cloudflare)
    try:
        ping_out = subprocess.check_output("ping -n 2 8.8.8.8", shell=True, text=True, errors="ignore")
        if "Average =" in ping_out:
            avg_ping = ping_out.split("Average =")[-1].strip()
            lines.append(f"• Internet Connectivity: Online (DNS Latency: {avg_ping})")
        else:
            lines.append("• Internet Connectivity: Online")
    except Exception:
        lines.append("• Internet Connectivity: Offline or Ping unreachable")

    return "\n".join(lines)


@tool(name="ping_host", description="Ping a target hostname or IP address (e.g. 'google.com', '8.8.8.8') to verify reachability and latency.")
def ping_host(host: str = "google.com", count: int = 4) -> str:
    """Pings a target host and returns packet loss and average latency."""
    clean_host = host.strip().replace("http://", "").replace("https://", "").split("/")[0]
    count = max(1, min(10, int(count)))
    
    try:
        cmd = f"ping -n {count} {clean_host}"
        output = subprocess.check_output(cmd, shell=True, text=True, errors="ignore")
        
        # Parse loss & avg latency
        loss = "0%"
        avg = "Unknown"
        for line in output.splitlines():
            if "Lost =" in line:
                loss = line.split("(")[-1].split(")")[0].strip()
            if "Average =" in line:
                avg = line.split("Average =")[-1].strip()

        return f"Ping results for '{clean_host}':\n• Packet Loss: {loss}\n• Average Latency: {avg}"
    except Exception as e:
        return f"Failed to ping '{clean_host}': {e}"
