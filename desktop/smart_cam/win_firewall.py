"""Windows: inbound firewall rules for Smart Cam (TCP ports + program/UDP for WebRTC)."""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys
from pathlib import Path

PROGRAM_RULE_NAME = "Smart Cam inbound (app)"
TCP_RULE_PREFIX = "Smart Cam TCP"

DEFAULT_TCP_PORTS: tuple[int, ...] = (17777, 17778, 17776)


def app_executable_path() -> Path:
    """Path used in firewall program rules (frozen exe or current Python)."""
    return Path(sys.executable).resolve()


def _is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _run_netsh(netsh: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(netsh), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def _netsh_path() -> Path | None:
    netsh = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "netsh.exe"
    return netsh if netsh.is_file() else None


def _netsh_report_success(returncode: int, output: str) -> bool:
    if returncode != 0:
        return False
    low = output.lower()
    if (
        "не найден" in low
        or "not found" in low
        or "no rules match" in low
        or "совпадающих правил не найдено" in low
    ):
        return False
    if (
        "ok" in low
        or "ок" in low
        or "already exists" in low
        or "уже существует" in low
        or "обновлен" in low
        or "updated" in low
    ):
        return True
    return True


def _rule_exists(netsh: Path, rule_name: str) -> bool:
    show = _run_netsh(
        netsh,
        ["advfirewall", "firewall", "show", "rule", f"name={rule_name}"],
    )
    if show.returncode != 0:
        return False
    low = ((show.stdout or "") + (show.stderr or "")).lower()
    return "no rules match" not in low and "совпадающих правил не найдено" not in low


def _add_or_enable_rule(netsh: Path, add_args: list[str], rule_name: str) -> tuple[bool, str]:
    add = _run_netsh(netsh, add_args)
    out = (add.stdout or "") + ("\n" + add.stderr if add.stderr else "")
    if _netsh_report_success(add.returncode, out):
        return True, ""
    setp = _run_netsh(
        netsh,
        [
            "advfirewall",
            "firewall",
            "set",
            "rule",
            f"name={rule_name}",
            "new",
            "enable=yes",
            "profile=any",
        ],
    )
    out2 = (setp.stdout or "") + ("\n" + setp.stderr if setp.stderr else "")
    if _netsh_report_success(setp.returncode, out2):
        return True, ""
    return False, out2.strip() or out.strip() or f"netsh code {add.returncode}"


def _program_rule_add_args(program: Path) -> list[str]:
    # Inbound for this exe: TCP (signaling/stream) + UDP (WebRTC ICE/media).
    return [
        "advfirewall",
        "firewall",
        "add",
        "rule",
        f"name={PROGRAM_RULE_NAME}",
        "dir=in",
        "action=allow",
        f"program={program}",
        "enable=yes",
        "profile=any",
    ]


def _tcp_port_rule_add_args(port: int) -> list[str]:
    rule = f"{TCP_RULE_PREFIX} {port}"
    return [
        "advfirewall",
        "firewall",
        "add",
        "rule",
        f"name={rule}",
        "dir=in",
        "action=allow",
        "protocol=TCP",
        f"localport={port}",
        "enable=yes",
        "profile=any",
    ]


def firewall_rules_configured(
    tcp_ports: tuple[int, ...] = DEFAULT_TCP_PORTS,
    *,
    require_program_rule: bool = True,
) -> bool:
    if sys.platform != "win32":
        return True
    netsh = _netsh_path()
    if netsh is None:
        return False
    if require_program_rule and not _rule_exists(netsh, PROGRAM_RULE_NAME):
        return False
    for port in tcp_ports:
        if not _rule_exists(netsh, f"{TCP_RULE_PREFIX} {port}"):
            return False
    return True


def ensure_windows_firewall_rules(
    *,
    program: Path | None = None,
    tcp_ports: tuple[int, ...] = DEFAULT_TCP_PORTS,
    allow_uac_elevate: bool = True,
) -> tuple[bool, str]:
    """
  Создаёт правила брандмауэра Windows:
  - входящие для exe (TCP+UDP, в т.ч. WebRTC);
  - входящие TCP на порты потока/сигналинга/обнаружения.
  """
    if sys.platform != "win32":
        return True, ""
    if not tcp_ports:
        tcp_ports = DEFAULT_TCP_PORTS
    for port in tcp_ports:
        if not (1024 <= port <= 65535):
            return False, f"Некорректный порт: {port}"

    netsh = _netsh_path()
    if netsh is None:
        return False, "Не найден netsh.exe."

    program = (program or app_executable_path()).resolve()
    if not program.is_file():
        return False, f"Не найден файл приложения: {program}"

    if firewall_rules_configured(tcp_ports):
        return True, "Правила брандмауэра уже настроены."

    if _is_admin():
        return _apply_rules(netsh, program, tcp_ports)

    if not allow_uac_elevate:
        return False, "Нужны права администратора для настройки брандмауэра."

    return _apply_rules_elevated(netsh, program, tcp_ports)


def _apply_rules(
    netsh: Path, program: Path, tcp_ports: tuple[int, ...]
) -> tuple[bool, str]:
    errors: list[str] = []

    ok, msg = _add_or_enable_rule(
        netsh, _program_rule_add_args(program), PROGRAM_RULE_NAME
    )
    if not ok:
        errors.append(f"{PROGRAM_RULE_NAME}: {msg}")

    for port in tcp_ports:
        rule = f"{TCP_RULE_PREFIX} {port}"
        ok, msg = _add_or_enable_rule(netsh, _tcp_port_rule_add_args(port), rule)
        if not ok:
            errors.append(f"{rule}: {msg}")

    if errors:
        return False, "\n".join(errors)
    return True, (
        "Брандмауэр: разрешены входящие TCP "
        f"{', '.join(str(p) for p in tcp_ports)} и UDP/TCP для приложения "
        f"(WebRTC по Wi‑Fi)."
    )


def _apply_rules_elevated(
    netsh: Path, program: Path, tcp_ports: tuple[int, ...]
) -> tuple[bool, str]:
    prog = str(program)
    parts: list[str] = [
        f'"{netsh}" advfirewall firewall add rule name="{PROGRAM_RULE_NAME}" '
        f'dir=in action=allow program="{prog}" enable=yes profile=any'
    ]
    for port in tcp_ports:
        rule = f"{TCP_RULE_PREFIX} {port}"
        parts.append(
            f'"{netsh}" advfirewall firewall add rule name="{rule}" dir=in '
            f"action=allow protocol=TCP localport={port} enable=yes profile=any"
        )
    params = "/c " + " & ".join(parts)
    rc = int(
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", "cmd.exe", params, None, 0
        )
    )
    if rc <= 32:
        if rc == 1223:
            return False, "Запрос UAC отменён — WebRTC по Wi‑Fi может не работать."
        return False, f"Не удалось открыть запрос UAC (код {rc})."
    return True, (
        "Подтвердите запрос UAC, чтобы Smart Cam мог принимать TCP и UDP "
        "(трансляция по Wi‑Fi / WebRTC)."
    )


def launch_elevated_inbound_tcp_rule(port: int) -> tuple[bool, str]:
    """Legacy: одно TCP-правило на порт (совместимость)."""
    return ensure_windows_firewall_rules(tcp_ports=(port,))
