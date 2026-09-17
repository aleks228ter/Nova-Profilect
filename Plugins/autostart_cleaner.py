"""Nova plugin: чистка автозагрузки пользователя без админ-прав."""
import os
import sys
import json
import shutil
import pathlib
from typing import Any

IS_WIN = sys.platform.startswith("win")

try:
    import winreg as _winreg  # type: ignore
except ImportError:
    _winreg = None  # type: ignore

winreg: Any = _winreg

PLUGIN = {
    "name": "Автозагрузка",
    "description": ("Показывает и убирает записи автозапуска текущего пользователя "
                    "(HKCU\\...\\Run, RunOnce и папка Startup). Не требует прав "
                    "администратора. Перед удалением делает резервную копию "
                    "в plugins/_backup/."),
}

RUN_KEYS = [
    (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run"),
    (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\RunOnce"),
] if IS_WIN else []

BACKUP_DIR = pathlib.Path(__file__).parent / "_backup"


def _startup_dir() -> pathlib.Path:
    return pathlib.Path(os.environ.get("APPDATA", "")) / \
           "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def _list_registry():
    items = []
    for hive, path in RUN_KEYS:
        try:
            with winreg.OpenKey(hive, path, 0, winreg.KEY_READ) as k:
                i = 0
                while True:
                    try:
                        name, val, _ = winreg.EnumValue(k, i)
                        i += 1
                        items.append((name, val))
                    except OSError:
                        break
        except Exception:
            pass
    return items


def scan():
    if not IS_WIN:
        return [{"id": "na", "title": "Только Windows", "severity": "info",
                 "detail": "Плагин работает только на Windows.",
                 "can_fix": False}]
    issues = []
    for name, val in _list_registry():
        issues.append({"id": f"reg::{name}",
                       "title": f"Автозапуск: {name}",
                       "severity": "warn",
                       "detail": f"Команда: {val}",
                       "can_fix": True})
    sd = _startup_dir()
    if sd.exists():
        for f in sd.iterdir():
            if f.name.lower() == "desktop.ini":
                continue
            issues.append({"id": f"file::{f.name}",
                           "title": f"Startup: {f.name}",
                           "severity": "warn",
                           "detail": f"Файл: {f}",
                           "can_fix": True})
    return issues


def _backup_reg(name, value):
    BACKUP_DIR.mkdir(exist_ok=True)
    f = BACKUP_DIR / "registry.json"
    data = []
    if f.exists():
        try:
            data = json.loads(f.read_text("utf-8"))
        except Exception:
            data = []
    data.append({"name": name, "value": value})
    f.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")


def _backup_file(path: pathlib.Path):
    dst = BACKUP_DIR / "startup"
    dst.mkdir(parents=True, exist_ok=True)
    try:
        shutil.move(str(path), str(dst / path.name))
    except Exception:
        shutil.copy2(str(path), str(dst / path.name))
        os.remove(path)


def fix(issue_id: str):
    if issue_id.startswith("reg::"):
        name = issue_id[5:]
        for hive, path in RUN_KEYS:
            try:
                with winreg.OpenKey(hive, path, 0, winreg.KEY_ALL_ACCESS) as k:
                    try:
                        val, _ = winreg.QueryValueEx(k, name)
                    except FileNotFoundError:
                        continue
                    _backup_reg(name, val)
                    winreg.DeleteValue(k, name)
                    return True, (f"Удалено: {name}\n"
                                  "Резерв: plugins/_backup/registry.json")
            except Exception as e:
                return False, f"Не удалось: {e}"
        return False, "Запись не найдена."
    if issue_id.startswith("file::"):
        fname = issue_id[6:]
        f = _startup_dir() / fname
        if not f.exists():
            return False, "Файл уже отсутствует."
        try:
            _backup_file(f)
            return True, (f"Убрано: {fname}\n"
                          "Резерв: plugins/_backup/startup/")
        except Exception as e:
            return False, f"Не удалось: {e}"
    return False, "Неизвестный тип."