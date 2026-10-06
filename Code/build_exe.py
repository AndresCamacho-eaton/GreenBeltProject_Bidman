"""
    Genera "BidMan Pick Optimizer.exe": un solo archivo que corre sin tener Python instalado.

    Uso (desde la carpeta del proyecto, con el venv que tiene PyInstaller y Pillow):
        .\venv\Scripts\python.exe Code\build_exe.py                      (usa Code\app_icon.ico)
        .\venv\Scripts\python.exe Code\build_exe.py C:\ruta\icono.png    (cambia el icono)

    El icono puede ser .ico, .png o .jpg (se convierte a .ico y se guarda como
    Code\app_icon.ico para las siguientes compilaciones).
    Resultado: dist\BidMan Pick Optimizer.exe
"""

import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)
ICON = os.path.join(HERE, "app_icon.ico")
BUILD = os.path.join(PROJECT, "build")
DIST = os.path.join(PROJECT, "dist")

RELEASES = os.path.join(PROJECT, "RELEASES.md")

sys.path.insert(0, HERE)
from app_info import APP_NAME, APP_VERSION, AUTHOR, AUTHOR_EMAIL, COMPANY, COPYRIGHT, SPECIAL_THANKS

# ===================================================================================================

def prepareIcon(source):

    # Deja el icono en Code\app_icon.ico. Un .png/.jpg se convierte con varios tamaños para que
    # Windows lo vea nítido en el Explorador y en la barra de tareas.
    if source is None:
        return ICON if os.path.exists(ICON) else None
    if not os.path.isfile(source):
        sys.exit(f"Icon not found: {source}")
    if source.lower().endswith(".ico"):
        if os.path.abspath(source) != ICON:
            shutil.copyfile(source, ICON)
        return ICON

    from PIL import Image
    image = Image.open(source).convert("RGBA")
    side = max(image.size)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.paste(image, ((side - image.width) // 2, (side - image.height) // 2))
    square.save(ICON, sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
    return ICON

# ---------------------------------------------------------------------------------------------------

def versionFile():

    # Nombre, versión, empresa, copyright y autor que Windows muestra en Propiedades > Detalles.
    numbers = tuple(int(n) for n in APP_VERSION.split(".")) + (0,)
    thanks = f" Special thanks to {', '.join(SPECIAL_THANKS)}." if SPECIAL_THANKS else ""
    path = os.path.join(BUILD, "version_info.txt")
    os.makedirs(BUILD, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={numbers}, prodvers={numbers}),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', '{COMPANY}'),
      StringStruct('FileDescription', '{APP_NAME} - created by {AUTHOR}'),
      StringStruct('ProductName', '{APP_NAME}'),
      StringStruct('FileVersion', '{APP_VERSION}'),
      StringStruct('ProductVersion', '{APP_VERSION}'),
      StringStruct('LegalCopyright', '{COPYRIGHT}'),
      StringStruct('Comments', 'Created by {AUTHOR} ({AUTHOR_EMAIL}).{thanks}'),
      StringStruct('OriginalFilename', '{APP_NAME}.exe'),
      StringStruct('InternalName', '{APP_NAME}')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
""")
    return path

# ---------------------------------------------------------------------------------------------------

def main():

    import PyInstaller.__main__

    icon = prepareIcon(sys.argv[1] if len(sys.argv) > 1 else None)
    args = [
        os.path.join(HERE, "OptimizePrnMenu.py"),
        "--onefile", "--console", "--clean", "--noconfirm",
        "--name", APP_NAME,
        "--version-file", versionFile(),
        "--paths", HERE,
        "--distpath", DIST,
        "--workpath", os.path.join(BUILD, "pyinstaller"),
        "--specpath", BUILD,
        # Las pruebas no van en el .exe; numpy/pandas están en el venv pero no se usan.
        "--exclude-module", "test_BidManMaintenanceToolsV1_4_0",
        "--exclude-module", "numpy",
        "--exclude-module", "pandas",
    ]
    if icon:
        args += ["--icon", icon]
    else:
        print("No icon given and no Code\\app_icon.ico: building with the default icon.")

    PyInstaller.__main__.run(args)
    exe = os.path.join(DIST, APP_NAME + ".exe")
    print(f"\nDone: {exe}")
    recordRelease(exe)

# ---------------------------------------------------------------------------------------------------

def recordRelease(exe):

    """
        Huella SHA-256 del .exe, guardada con fecha y versión en RELEASES.md. Con el historial de
        git, sirve para demostrar qué compilación exacta salió de aquí, cuándo y de quién.
    """

    import hashlib
    import time

    digest = hashlib.sha256()
    with open(exe, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    sha = digest.hexdigest()
    size = os.path.getsize(exe)
    when = time.strftime("%Y-%m-%d %H:%M")

    if not os.path.exists(RELEASES):
        with open(RELEASES, "w", encoding="utf-8") as fh:
            fh.write(f"# {APP_NAME} - builds\n\n"
                     f"Every build of the app, with its SHA-256 fingerprint. To check that a copy of "
                     f"the .exe is one of these builds, run in PowerShell:\n\n"
                     f"    Get-FileHash \"{APP_NAME}.exe\"\n\n"
                     f"and compare the hash with the table.\n\n"
                     f"| Date | Version | Author | Size (bytes) | SHA-256 |\n"
                     f"|---|---|---|---|---|\n")
    with open(RELEASES, "a", encoding="utf-8") as fh:
        fh.write(f"| {when} | {APP_VERSION} | {AUTHOR} | {size:,} | `{sha}` |\n")

    print(f"SHA-256: {sha}")
    print(f"Recorded in {RELEASES}")

if __name__ == "__main__":
    main()
