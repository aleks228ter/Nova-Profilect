"""Nova plugin: находит сторонние антивирусы и помогает их удалить."""
import subprocess
import sys
from typing import Any

IS_WIN = sys.platform.startswith("win")

try:
    import winreg as _winreg  # type: ignore
except ImportError:
    _winreg = None  # type: ignore

winreg: Any = _winreg

PLUGIN = {
    "name": "Сторонний антивирус",
    "description": ("Находит сторонние антивирусы (360, Avast, AVG, Kaspersky, ESET и др.). "
                    "Удаление требует прав администратора — Nova запустит официальный "
                    "деинсталлятор, а Windows запросит UAC."),
}

KNOWN = ["360", "avast", "avg", "kaspersky", "drweb", "dr.web", "eset",
         "mcafee", "norton", "bitdefender", "malwarebytes", "comodo",
         "trend micro", "panda", "avira"]

UNINSTALL_ROOTS = [
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
    (winreg.HKEY_CURRENT_USER,  r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
] if IS_WIN else []


def _detect_av():
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance -Namespace root/SecurityCenter2 -ClassName AntiVirusProduct "
             "| Select-Object -ExpandProperty displayName"],
            capture_output=True, text=True, timeout=15)
        return [l.strip() for l in out.stdout.splitlines() if l.strip()]
    except Exception:
        return []


def _find_uninstall(keyword: str):
    kw = keyword.lower()
    for hive, root in UNINSTALL_ROOTS:
        try:
            with winreg.OpenKey(hive, root) as k:
                i = 0
                while True:
                    try:
                        sub = winreg.EnumKey(k, i)
                        i += 1
                    except OSError:
                        break
                    try:
                        with winreg.OpenKey(hive, root + "\\" + sub) as sk:
                            try:
                                disp, _ = winreg.QueryValueEx(sk, "DisplayName")
                            except FileNotFoundError:
                                continue
                            if not disp or kw not in disp.lower():
                                continue
                            try:
                                us, _ = winreg.QueryValueEx(sk, "UninstallString")
                            except FileNotFoundError:
                                us = ""
                            return disp, us
                    except Exception:
                        continue
        except Exception:
            continue
    return None, ""


def scan():
    if not IS_WIN:
        return [{"id": "na", "title": "Только Windows", "severity": "info",
                 "detail": "Плагин работает только на Windows.",
                 "can_fix": False}]
    avs = _detect_av()
    if not avs:
        return [{"id": "av::none",
                 "title": "Сторонних антивирусов не видно",
                 "severity": "info",
                 "detail": ("SecurityCenter2 не вернул список. "
                            "Скорее всего используется только Microsoft Defender."),
                 "can_fix": False}]
    issues = []
    for name in avs:
        low = name.lower()
        if "microsoft" in low or "windows defender" in low:
            continue
        key = next((k for k in KNOWN if k in low), None)
        disp, uninst = _find_uninstall(key or name.split()[0])
        detail = f"Обнаружено: {name}\n"
        if uninst:
            detail += f"Деинсталлятор: {uninst}\n"
        detail += ("Удаление потребует прав администратора — "
                   "Nova запустит штатный деинсталлятор, UAC спросит подтверждение.")
        issues.append({"id": f"av::{name}",
                       "title": f"Сторонний антивирус: {name}",
                       "severity": "warn",
                       "detail": detail,
                       "can_fix": bool(uninst)})
    return issues


def fix(issue_id: str):
    if not issue_id.startswith("av::"):
        return False, "Неизвестный ID."
    name = issue_id[4:]
    low = name.lower()
    key = next((k for k in KNOWN if k in low), None)
    disp, uninst = _find_uninstall(key or name.split()[0])
    if not uninst:
        return False, (f"Деинсталлятор «{name}» не найден.\n"
                       "Откройте вручную: Win+R → appwiz.cpl → "
                       "выберите программу → Удалить.")
    try:
        subprocess.Popen(uninst, shell=True)
        return True, (f"Запущен деинсталлятор «{disp}».\n"
                      "Пройдите шаги мастера. UAC запросит подтверждение — "
                      "это нормально.")
    except Exception as e:
        return False, f"Не удалось запустить деинсталлятор: {e}"