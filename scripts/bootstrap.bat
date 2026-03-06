@echo off
title FranklinOps Bootstrap
cd /d "%~dp0.."
powershell -ExecutionPolicy Bypass -File "%~dp0bootstrap.ps1"
pause
