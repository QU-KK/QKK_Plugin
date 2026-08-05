@echo off

@REM Dependencias (Las versiones importan) (copiar y pegar estas 3 lineas en Powershell (para q lo ejecute el string necesita el & delante)):
@REM & "$Env:localappdata\Programs\Python\Python311\python.exe" -m pip install --upgrade pip
@REM & "$Env:localappdata\Programs\Python\Python311\python.exe" -m pip install numpy==1.25.2
@REM & "$Env:localappdata\Programs\Python\Python311\python.exe" -m pip install Cython==0.29.36 

IF EXIST distances_win.html (
    del distances_win.html
)

IF EXIST distances_win.c (
    del distances_win.c
)

IF EXIST build (
    rd /s /q build
)

IF EXIST distances_win.pyd (
    del distances_win.pyd
)

"%LocalAppData%\Programs\Python\Python311\python.exe" setup.py build_ext --inplace

IF EXIST distances_win.c (
    del distances_win.c
)

IF EXIST build (
    rd /s /q build
)

IF EXIST distances_win.cpp (
    del distances_win.cpp
)

IF EXIST distances_win.cp311-win_amd64.pyd (
    ren distances_win.cp311-win_amd64.pyd distances_win.pyd
)

IF EXIST distances.c (
    del distances.c
)

pause