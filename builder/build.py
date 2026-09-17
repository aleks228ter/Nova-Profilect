"""
Nova — сборка в .exe через PyInstaller.
Правь только блок AUTHOR ниже, остальное работает само.

Запуск:  python build.py
"""

import subprocess
import sys
import pathlib
import shutil

# ──────────────────────────────────────────────────────────────────────────
#   ЗАПОЛНИ ЭТО
# ──────────────────────────────────────────────────────────────────────────
AUTHOR = {
    "name":     "Алексей Соколов",              # твоё имя или ник
    "email":    "AleksAokolzonirz@yandex.ru",          # почта
    "url":      "https://github.com/aleks228ter/Nova-Profilect",      # сайт / GitHub / Telegram
    "company":  "Nova Profilect",             # название проекта/студии
    "copyright": "© 2026 Соколов.А.А. Все права защищены.",
    "license":  "MIT",                       # лицензия (для справки)
    "comment":  "Лёгкий помощник для поиска уязвимостей в ОС",
}

APP = {
    "name":     "Nova",
    "version":  "1.0.0.0",                   # формат X.X.X.X для Windows
    "entry":    "Nova.py",
    "icon":     "nova.ico",                  # положи рядом, иначе пропустится
    "onefile":  True,                        # True = один .exe
    "console":  False,                       # False = без чёрного окна
}
# ──────────────────────────────────────────────────────────────────────────

import sys
import pathlib

def find_project_root(start: pathlib.Path) -> pathlib.Path:
    """Ищет папку, где лежит Nova.py — вверх по дереву от build.py."""
    entry_name = "Nova.py"
    for p in [start, *start.parents]:
        if (p / entry_name).exists():
            return p
    # fallback — папка самого build.py
    return start

BASE = find_project_root(pathlib.Path(__file__).resolve().parent)
VERSION_FILE = BASE / "version_info.txt"
BUILD_DIR = BASE / "build"
DIST_DIR = BASE / "dist"


def make_version_info() -> pathlib.Path:
    """Генерирует version_info.txt для PyInstaller с данными автора."""
    v = APP["version"].split(".")
    while len(v) < 4:
        v.append("0")
    v = tuple(int(x) for x in v[:4])

    content = f'''# UTF-8
# Метаданные .exe — вшиваются в свойства файла (вкладка «Подробно»).
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={v},
    prodvers={v},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '040904B0',
        [StringStruct('CompanyName',      '{AUTHOR["company"]}'),
         StringStruct('FileDescription',  '{AUTHOR["comment"]}'),
         StringStruct('FileVersion',      '{APP["version"]}'),
         StringStruct('InternalName',     '{APP["name"]}'),
         StringStruct('LegalCopyright',   '{AUTHOR["copyright"]}'),
         StringStruct('OriginalFilename', '{APP["name"]}.exe'),
         StringStruct('ProductName',      '{APP["name"]}'),
         StringStruct('ProductVersion',   '{APP["version"]}'),
         StringStruct('Author',           '{AUTHOR["name"]}'),
         StringStruct('Comments',         'License: {AUTHOR["license"]} | {AUTHOR["url"]}')
        ])
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
'''
    VERSION_FILE.write_text(content, encoding="utf-8")
    print(f"[Nova] создан {VERSION_FILE.name}")
    return VERSION_FILE


def ensure_pyinstaller():
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("[Nova] PyInstaller не установлен, ставлю...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])


def clean():
    for d in (BUILD_DIR, DIST_DIR):
        if d.exists():
            shutil.rmtree(d)
    for f in (BASE / f"{APP['name']}.spec",):
        if f.exists():
            f.unlink()


def build():
    entry = BASE / APP["entry"]
    if not entry.exists():
        print(f"[Nova] Ошибка: не найден {entry}")
        sys.exit(1)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--name", APP["name"],
        "--version-file", str(VERSION_FILE),
        "--add-data", f"plugins{';' if sys.platform.startswith('win') else ':'}plugins",
    ]

    if APP["onefile"]:
        cmd.append("--onefile")
    if not APP["console"]:
        cmd.append("--windowed")

    icon = BASE / APP["icon"]
    if icon.exists():
        cmd += ["--icon", str(icon)]
    else:
        print(f"[Nova] иконка {APP['icon']} не найдена — соберу без неё")

    cmd.append(str(entry))
    print("[Nova] команда:", " ".join(cmd))
    subprocess.check_call(cmd)

    exe = DIST_DIR / f"{APP['name']}.exe"
    if exe.exists():
        size = exe.stat().st_size / 1024 / 1024
        print()
        print("=" * 60)
        print(f"  Готово: {exe}")
        print(f"  Размер: {size:.1f} МБ")
        print(f"  Автор:  {AUTHOR['name']}  <{AUTHOR['email']}>")
        print(f"  Сайт:   {AUTHOR['url']}")
        print(f"  Версия: {APP['version']}")
        print("=" * 60)
        print()
        print("Свойства .exe → вкладка «Подробно» покажут автора,")
        print("версию и копирайт.")
    else:
        print("[Nova] Что-то пошло не так, .exe не найден.")


if __name__ == "__main__":
    ensure_pyinstaller()
    make_version_info()
    clean()
    build()