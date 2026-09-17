"""
Nova — лёгкий помощник для поиска уязвимостей и слабых мест в ОС.
Без прав администратора. Только чтение системных параметров + безопасные
пользовательские правки с резервными копиями.

Запуск:  python Nova.py
"""

import os
import sys
import platform
import subprocess
import pathlib
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Any

IS_WIN = sys.platform.startswith("win")
BASE_DIR = pathlib.Path(__file__).resolve().parent
PLUGINS_DIR = BASE_DIR / "plugins"
BACKUP_DIR = PLUGINS_DIR / "_backup"


# ──────────────────────────────────────────────────────────────────────────
#   Утилиты
# ──────────────────────────────────────────────────────────────────────────
def run(cmd, timeout: int = 10) -> str:
    """Безопасный запуск команды, всегда возвращает строку."""
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=timeout, shell=isinstance(cmd, str)
        )
        return (r.stdout or "") + (r.stderr or "")
    except Exception:
        return ""


# ──────────────────────────────────────────────────────────────────────────
#   Встроенные проверки
# ──────────────────────────────────────────────────────────────────────────
def check_uac():
    if not IS_WIN:
        return ("skip", "UAC (только Windows)", "")
    out = run('reg query "HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System" /v EnableLUA')
    if "0x1" in out:
        return ("ok", "UAC включён", "Контроль учётных записей активен.")
    if "0x0" in out:
        return ("fail", "UAC выключен",
                "Включите UAC: Панель управления → Учётные записи → "
                "Изменение параметров контроля учётных записей → "
                "ползунок на второй уровень сверху.")
    return ("warn", "UAC: не удалось определить",
            "Проверьте вручную в параметрах системы.")


def check_firewall():
    if not IS_WIN:
        return ("skip", "Брандмауэр (только Windows)", "")
    out = run("netsh advfirewall show allprofiles state").lower()
    if "off" in out:
        return ("fail", "Брандмауэр выключен",
                "Включите: Параметры → Сеть и Интернет → Брандмауэр Windows → "
                "включить для всех профилей.")
    if "on" in out:
        return ("ok", "Брандмауэр включён", "Сетевой экран активен.")
    return ("warn", "Брандмауэр: нет данных", "Проверьте вручную.")


def check_antivirus():
    if not IS_WIN:
        return ("skip", "Антивирус (только Windows)", "")
    out = run('powershell -NoProfile -Command '
              '"Get-CimInstance -Namespace root/SecurityCenter2 '
              '-ClassName AntiVirusProduct | '
              'Select-Object -ExpandProperty displayName"')
    names = [l.strip() for l in out.splitlines() if l.strip()]
    if names:
        return ("ok", f"Антивирус: {', '.join(names[:2])}",
                "Защита в реальном времени присутствует.")
    return ("fail", "Антивирус не обнаружен",
            "Включите Microsoft Defender или установите антивирус.")


def check_autostart():
    if not IS_WIN:
        return ("skip", "Автозагрузка (только Windows)", "")
    out = run('reg query "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run"')
    n = len([l for l in out.splitlines() if "REG_SZ" in l])
    if n <= 4:
        return ("ok", f"Автозагрузка: {n} записей",
                "Подозрительных записей не видно.")
    if n <= 8:
        return ("warn", f"Автозагрузка: {n} записей",
                "Много программ стартует с системой. "
                "Проверьте: Диспетчер задач → Автозагрузка. "
                "Лишнее удобно чистить плагином «Автозагрузка».")
    return ("fail", f"Автозагрузка: {n} записей",
            "Слишком много автозапуска. Откройте плагин «Автозагрузка» "
            "и отключите лишнее.")


def check_ports():
    if not IS_WIN:
        return ("skip", "Порты (только Windows)", "")
    out = run("netstat -ano -p tcp")
    n = len([l for l in out.splitlines() if "LISTENING" in l and "0.0.0.0:" in l])
    if n < 10:
        return ("ok", f"Открыто портов: {n}", "Нормально для домашнего ПК.")
    if n < 20:
        return ("warn", f"Открыто портов: {n}",
                "Много слушающих сервисов. Если не запускали серверов — "
                "проверьте: netstat -ano | findstr LISTENING")
    return ("fail", f"Открыто портов: {n}",
            "Подозрительно много. Запустите: "
            "netstat -ano | findstr LISTENING и проверьте процессы.")


def check_guest():
    if not IS_WIN:
        return ("skip", "Гостевая учётка (только Windows)", "")
    out = run("net user guest").lower()
    for line in out.splitlines():
        if "account active" in line and "yes" in line:
            return ("fail", "Гостевая учётка активна",
                    "Отключите Guest в Учётных записях.")
    return ("ok", "Гостевая учётка отключена", "Доступ по сети закрыт.")


def check_version():
    rel = platform.release()
    if IS_WIN and rel in ("10", "11"):
        return ("ok", f"Windows {rel}", "Проверяйте обновления.")
    return ("warn", f"ОС: {platform.system()} {rel}",
            "Убедитесь, что система получает обновления безопасности.")


CHECKS = [check_uac, check_firewall, check_antivirus,
          check_autostart, check_ports, check_guest, check_version]

ICONS = {"ok": "✓", "warn": "!", "fail": "✗", "skip": "–"}
COLORS = {"ok": "#1a7f37", "warn": "#b58900", "fail": "#c0392b", "skip": "#888"}


# ──────────────────────────────────────────────────────────────────────────
#   Загрузка внешних плагинов из plugins/*.py
# ──────────────────────────────────────────────────────────────────────────
def load_external_plugins() -> list[Any]:
    """Плагин — это .py-модуль с PLUGIN (dict), scan() и fix(id)."""
    import importlib.util
    found: list[Any] = []
    PLUGINS_DIR.mkdir(parents=True, exist_ok=True)
    for f in sorted(PLUGINS_DIR.glob("*.py")):
        if f.name.startswith("_"):
            continue
        try:
            spec = importlib.util.spec_from_file_location(
                f"nova_ext_{f.stem}", f)
            if spec is None or spec.loader is None:
                print(f"[Nova] плагин {f.name}: не удалось получить spec")
                continue
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            if all(hasattr(mod, a) for a in ("PLUGIN", "scan", "fix")):
                found.append(mod)
        except Exception as e:
            print(f"[Nova] внешний плагин {f.name} не загружен: {e}")
    return found


# ──────────────────────────────────────────────────────────────────────────
#   Окно плагина
# ──────────────────────────────────────────────────────────────────────────
class PluginWindow(tk.Toplevel):
    def __init__(self, master, plugin):
        super().__init__(master)
        self.plugin = plugin
        info = getattr(plugin, "PLUGIN", {}) or {}
        self.title(f"Nova — {info.get('name', 'Плагин')}")
        self.geometry("620x480")
        self.minsize(500, 380)
        self.transient(master)

        ttk.Label(self, text=info.get("description", ""),
                  wraplength=580, padding=10).pack(fill="x")

        row = ttk.Frame(self, padding=(10, 0))
        row.pack(fill="x")
        ttk.Button(row, text="Сканировать", command=self.refresh).pack(side="left")
        self.fix_btn = ttk.Button(row, text="Исправить",
                                  command=self.do_fix, state="disabled")
        self.fix_btn.pack(side="left", padx=6)

        self.listbox = tk.Listbox(self, font=("Consolas", 10),
                                  activestyle="none", borderwidth=0,
                                  highlightthickness=0)
        self.listbox.pack(fill="both", expand=True, padx=10, pady=10)
        self.listbox.bind("<<ListboxSelect>>", self.on_select)

        self.status = ttk.Label(self, text="", padding=10, wraplength=580,
                                justify="left")
        self.status.pack(fill="x")

        self.issues: list[dict] = []
        self.refresh()

    def refresh(self):
        self.listbox.delete(0, tk.END)
        self.issues = []
        try:
            items = self.plugin.scan()
        except Exception as e:
            self.status.config(text=f"Ошибка сканирования: {e}")
            return
        marks = {"info": "•", "warn": "!", "danger": "✗"}
        for it in items:
            self.issues.append(it)
            self.listbox.insert(
                tk.END,
                f"  {marks.get(it.get('severity', 'info'), '•')}  {it['title']}"
            )
        if not items:
            self.listbox.insert(tk.END, "  ✓  Проблем не найдено")
        self.status.config(text=f"Найдено: {len(items)}")

    def on_select(self, _=None):
        sel = self.listbox.curselection()
        if not sel or not self.issues:
            self.fix_btn.config(state="disabled")
            return
        it = self.issues[sel[0]]
        self.fix_btn.config(state="normal" if it.get("can_fix") else "disabled")
        self.status.config(text=it.get("detail", ""))

    def do_fix(self):
        sel = self.listbox.curselection()
        if not sel:
            return
        it = self.issues[sel[0]]
        if not messagebox.askyesno(
                "Nova",
                f"{it['title']}\n\n{it.get('detail', '')}\n\nПрименить?"):
            return
        try:
            ok, msg = self.plugin.fix(it["id"])
        except Exception as e:
            ok, msg = False, str(e)
        messagebox.showinfo("Nova", msg)
        self.refresh()


# ──────────────────────────────────────────────────────────────────────────
#   Главное окно
# ──────────────────────────────────────────────────────────────────────────
class Nova(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Nova — проверка безопасности")
        self.geometry("740x660")
        self.minsize(620, 540)

        top = ttk.Frame(self, padding=10)
        top.pack(fill="x")
        ttk.Button(top, text="Проверить", command=self.run_checks).pack(side="left")
        self.summary = ttk.Label(top, text="Готов к проверке")
        self.summary.pack(side="right")

        mid = ttk.Frame(self, padding=(10, 0))
        mid.pack(fill="both", expand=True)
        self.listbox = tk.Listbox(mid, font=("Consolas", 11),
                                  activestyle="none", borderwidth=0,
                                  highlightthickness=0)
        self.listbox.pack(fill="both", expand=True)
        self.listbox.bind("<<ListboxSelect>>", self.show_advice)

        pbar = ttk.LabelFrame(self, text="Плагины", padding=8)
        pbar.pack(fill="x", padx=10, pady=(8, 0))

        self.plugins = load_external_plugins()

        if not self.plugins:
            ttk.Label(pbar, text="Плагинов нет.").pack(side="left")
        else:
            for plug in self.plugins:
                name = getattr(plug, "PLUGIN", {}).get("name", "Плагин")
                ttk.Button(pbar, text=name,
                           command=lambda p=plug: PluginWindow(self, p)
                           ).pack(side="left", padx=4)

        bottom = ttk.LabelFrame(self, text="Рекомендация", padding=10)
        bottom.pack(fill="x", padx=10, pady=10)
        self.advice = tk.Text(bottom, height=5, wrap="word", borderwidth=0,
                              background=self.cget("bg"),
                              font=("Segoe UI", 10))
        self.advice.pack(fill="x")
        self.advice.configure(state="disabled")

        self.results: list[tuple] = []

    def run_checks(self):
        self.listbox.delete(0, tk.END)
        self.results.clear()
        ok = warn = fail = 0
        for fn in CHECKS:
            try:
                status, title, advice = fn()
            except Exception as e:
                status, title, advice = "warn", f"Ошибка проверки: {e}", ""
            self.results.append((status, title, advice))
            self.listbox.insert(tk.END, f"  {ICONS[status]}  {title}")
            self.listbox.itemconfig(tk.END, foreground=COLORS[status])
            if status == "ok":
                ok += 1
            elif status == "warn":
                warn += 1
            elif status == "fail":
                fail += 1
        self.summary.config(text=f"✓ {ok}   ! {warn}   ✗ {fail}")
        if self.results:
            self.listbox.selection_set(0)
            self.show_advice()

    def show_advice(self, _=None):
        sel = self.listbox.curselection()
        if not sel:
            return
        _, _, advice = self.results[sel[0]]
        self.advice.configure(state="normal")
        self.advice.delete("1.0", tk.END)
        self.advice.insert(tk.END, advice or "Нет рекомендаций.")
        self.advice.configure(state="disabled")


# ──────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    Nova().mainloop()