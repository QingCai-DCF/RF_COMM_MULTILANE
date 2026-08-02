@echo off
call "D:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul
if errorlevel 1 exit /b %errorlevel%
cl /nologo /std:c11 /W4 /WX /I"C:\Users\user\Documents\RF_COMM_MULTILANE_P10_1R\software\ps_driver" /I"C:\Users\user\Documents\RF_COMM_MULTILANE_P10_1R\config\register_map\generated" "C:\Users\user\Documents\RF_COMM_MULTILANE_P10_1R\software\ps_driver\p8d_driver.c" "C:\Users\user\Documents\RF_COMM_MULTILANE_P10_1R\tests\p8d\p8d_driver_offline_test.c" /Fe:"C:\Users\user\Documents\RF_COMM_MULTILANE_P10_1R\evidence\generated\p10_1r_exact_source_p8d_8bb75904\p8d_raw\formal_8bb759047276\software\p8d_driver_offline_test.exe"
if errorlevel 1 exit /b %errorlevel%
"C:\Users\user\Documents\RF_COMM_MULTILANE_P10_1R\evidence\generated\p10_1r_exact_source_p8d_8bb75904\p8d_raw\formal_8bb759047276\software\p8d_driver_offline_test.exe"
exit /b %errorlevel%
