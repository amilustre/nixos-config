#!/usr/bin/env python3
"""ESP32 Dashboard API server for Hyprland and system info."""

import http.server
import json
import os
import subprocess
import time
import re

HOST = "0.0.0.0"
PORT = 8080


def hyprctl(args):
    """Run hyprctl with the correct instance signature."""
    # Try to discover HYPRLAND_INSTANCE_SIGNATURE from runtime dir
    sig = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
    if not sig:
        runtime_dir = os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
        hypr_dir = os.path.join(runtime_dir, "hypr")
        try:
            instances = sorted(os.listdir(hypr_dir), reverse=True)
            if instances:
                sig = instances[0]
        except (FileNotFoundError, PermissionError, IndexError):
            return {"error": "Could not find Hyprland instance signature"}

    env = os.environ.copy()
    env["HYPRLAND_INSTANCE_SIGNATURE"] = sig
    try:
        result = subprocess.run(
            ["hyprctl"] + args,
            capture_output=True,
            text=True,
            timeout=5,
            env=env,
        )
        return result.stdout
    except subprocess.TimeoutExpired:
        return json.dumps({"error": "hyprctl timed out"})
    except FileNotFoundError:
        return json.dumps({"error": "hyprctl not found"})


def run_cmd(cmd, timeout=5):
    """Run a shell command and return stdout."""
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, shell=True
        )
        return result.stdout.strip()
    except Exception as e:
        return str(e)


class DashboardHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Suppress default logging; or enable briefly: print(format % args)

    def _send_json(self, data, status=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_ok(self):
        self._send_json({"status": "ok"})

    def do_GET(self):
        parsed = self.path.rstrip("/")
        if parsed == "/workspaces":
            raw = hyprctl(["clients", "-j"])
            try:
                data = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                data = {"error": "Failed to parse hyprctl output", "raw": raw}
            self._send_json(data)

        elif parsed == "/workspace":
            raw = hyprctl(["activeworkspace", "-j"])
            try:
                data = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                data = {"error": "Failed to parse hyprctl output", "raw": raw}
            self._send_json(data)

        elif parsed == "/system":
            data = self._get_system_info()
            self._send_json(data)

        else:
            self._send_json({"error": "Not found"}, 404)

    def do_POST(self):
        parsed = self.path.rstrip("/")
        if parsed == "/workspace":
            # Default to workspace 1 if no number given
            hyprctl(["dispatch", "workspace", "1"])
            self._send_ok()

        elif parsed.startswith("/workspace/"):
            n = parsed.split("/workspace/")[-1]
            if n.isdigit():
                hyprctl(["dispatch", "workspace", n])
                self._send_ok()
            else:
                self._send_json({"error": f"Invalid workspace number: {n}"}, 400)

        elif parsed == "/volumen/up":
            run_cmd("pactl set-sink-volume @DEFAULT_SINK@ +5%")
            self._send_ok()

        elif parsed == "/volumen/down":
            run_cmd("pactl set-sink-volume @DEFAULT_SINK@ -5%")
            self._send_ok()

        elif parsed == "/volumen/mute":
            run_cmd("pactl set-sink-mute @DEFAULT_SINK@ toggle")
            self._send_ok()

        else:
            self._send_json({"error": "Not found"}, 404)

    def _get_system_info(self):
        info = {}

        # CPU temperature
        try:
            with open("/sys/class/thermal/thermal_zone0/temp") as f:
                temp_raw = f.read().strip()
                info["cpu_temp"] = round(int(temp_raw) / 1000, 1)
        except (FileNotFoundError, ValueError):
            # Try sensors command
            out = run_cmd("sensors -j 2>/dev/null || echo '{}'")
            info["cpu_temp_raw"] = out

        # RAM
        try:
            with open("/proc/meminfo") as f:
                meminfo = f.read()
            mem_total_match = re.search(r"MemTotal:\s+(\d+)", meminfo)
            mem_avail_match = re.search(r"MemAvailable:\s+(\d+)", meminfo)
            if mem_total_match and mem_avail_match:
                total_kb = int(mem_total_match.group(1))
                avail_kb = int(mem_avail_match.group(1))
                used_kb = total_kb - avail_kb
                info["ram"] = {
                    "total_gb": round(total_kb / (1024 * 1024), 1),
                    "used_gb": round(used_kb / (1024 * 1024), 1),
                    "used_percent": round((used_kb / total_kb) * 100, 1),
                }
        except (FileNotFoundError, ValueError):
            pass

        # Disk
        out = run_cmd("df -h / | tail -1")
        parts = out.split()
        if len(parts) >= 5:
            info["disk"] = {
                "size": parts[1],
                "used": parts[2],
                "avail": parts[3],
                "use_percent": parts[4],
            }

        return info


def main():
    server = http.server.HTTPServer((HOST, PORT), DashboardHandler)
    print(f"[dashboard-api] Listening on {HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("[dashboard-api] Shutting down")
        server.server_close()


if __name__ == "__main__":
    main()
