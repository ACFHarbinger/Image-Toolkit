@REM --- Standard Gradle Wrapper Script Content for Windows ---
@REM This script ensures Gradle is downloaded and executed using the correct version
@REM defined in gradle-wrapper.properties.

@if "%DEBUG%" == "" @echo off
@setlocal

@REM Set the path to the Java executable
if "%JAVA_HOME%" == "" (
set JAVA_CMD=java
) else (
set JAVA_CMD="%JAVA_HOME%\bin\java"
)

@REM Execute the wrapper
"%JAVA_CMD%" -Dorg.gradle.appname="%APP_NAME%" -classpath "%APP_HOME%\gradle\wrapper\gradle-wrapper.jar" org.gradle.wrapper.GradleWrapperMain %*

@if "%ERRORLEVEL%" NEQ "0" pause

@endlocal