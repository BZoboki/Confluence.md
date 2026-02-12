# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for confluence-md CLI."""

a = Analysis(
    ['src/confluence_md/__main__.py'],  # Entry point wrapper
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'requests', 'urllib3', 'certifi', 'bs4', 'lxml', 'yaml',
        'atlassian', 'atlassian.confluence', 'atlassian.rest_api_base'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='confluence-md',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # UPX compression worsens Windows Defender false positives
    console=True,
)
