@echo off
call "D:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul
if errorlevel 1 exit /b %errorlevel%
cl /nologo /std:c11 /W4 /WX /I"C:\Users\user\Documents\RF_COMM_MULTILANE_P9\software\ps_driver" /I"C:\Users\user\Documents\RF_COMM_MULTILANE_P9\config\register_map\generated" "C:\Users\user\Documents\RF_COMM_MULTILANE_P9\software\ps_driver\p8d_driver.c" "C:\Users\user\Documents\RF_COMM_MULTILANE_P9\tests\p8d\p8d_driver_offline_test.c" /Fe:"C:\Users\user\Documents\RF_COMM_MULTILANE_P9\evidence\generated\p8e_raw\r8d\p8d_raw\formal_56fbf42788dc\software\p8d_driver_offline_test.exe"
if errorlevel 1 exit /b %errorlevel%
"C:\Users\user\Documents\RF_COMM_MULTILANE_P9\evidence\generated\p8e_raw\r8d\p8d_raw\formal_56fbf42788dc\software\p8d_driver_offline_test.exe"
exit /b %errorlevel%
