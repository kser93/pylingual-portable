@echo off
rem Test-only fake OpenCode launcher. It creates a real PyLingual MCP session
rem and emits one JSON event, so scripts/opencode_harness.py can be tested
rem without an OpenCode installation. Do not use for evaluating a real agent.
call "%~dp0..\scripts\python.cmd" "%~dp0fake_opencode.py"
exit /b %ERRORLEVEL%
