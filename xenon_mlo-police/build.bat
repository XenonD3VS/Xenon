@echo off
REM Builds xenon_mlo-police: generates XML sources and converts them to binary files in .\stream
REM Requirements: Python 3 (numpy, pillow), git, .NET SDK 8+
cd /d "%~dp0"

echo [1/3] Generating XML sources...
python source\generate.py --out source\xml || goto :error

echo [2/3] Building converter (CodeWalker.Core)...
if not exist tools\CodeWalker (
  git clone --depth 1 https://github.com/dexyfex/CodeWalker tools\CodeWalker || goto :error
)
dotnet build tools\cwconv\cwconv.csproj -c Release -o tools\cwconv\bin >nul || goto :error

echo [3/3] Converting XML -^> binary (stream\)...
dotnet tools\cwconv\bin\cwconv.dll source\xml stream || goto :error
echo Done. Copy the xenon_mlo-police folder to your server resources and add: ensure xenon_mlo-police
goto :eof

:error
echo BUILD FAILED
exit /b 1
