@echo off
call "D:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul
if errorlevel 1 exit /b %errorlevel%
cl /nologo /std:c11 /W4 /WX /I"C:\Users\user\.codex\worktrees\3765\RF_COMM_MULTILANE\software\ps_driver" /I"C:\Users\user\.codex\worktrees\3765\RF_COMM_MULTILANE\config\register_map\generated" "C:\Users\user\.codex\worktrees\3765\RF_COMM_MULTILANE\software\ps_driver\p8d_driver.c" "C:\Users\user\.codex\worktrees\3765\RF_COMM_MULTILANE\tests\p8d\p8d_driver_offline_test.c" /Fe:"C:\Users\user\.codex\worktrees\3765\RF_COMM_MULTILANE\evidence\generated\p8d_raw\formal_cad58c79c22f\software\p8d_driver_offline_test.exe"
if errorlevel 1 exit /b %errorlevel%
"C:\Users\user\.codex\worktrees\3765\RF_COMM_MULTILANE\evidence\generated\p8d_raw\formal_cad58c79c22f\software\p8d_driver_offline_test.exe"
exit /b %errorlevel%
