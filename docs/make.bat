@ECHO OFF
setlocal

pushd %~dp0

REM Command file for Sphinx documentation

if "%SPHINXBUILD%" == "" (
	where uv >NUL 2>NUL
	if errorlevel 1 (
		set SPHINXBUILD=sphinx-build
	) else (
		set SPHINXBUILD=uv run --group docs sphinx-build
	)
)
set SOURCEDIR=.
set BUILDDIR=_build
set EXITCODE=0

%SPHINXBUILD% >NUL 2>NUL
if errorlevel 9009 (
	echo.
	echo.The 'sphinx-build' command was not found. Make sure you have Sphinx
	echo.installed, then set the SPHINXBUILD environment variable to point
	echo.to the full path of the 'sphinx-build' executable. Alternatively you
	echo.may add the Sphinx directory to PATH.
	echo.
	echo.If you don't have Sphinx installed, grab it from
	echo.https://www.sphinx-doc.org/
	set EXITCODE=1
	goto end
)

if "%1" == "" goto help

if "%1"=="fasthtml" goto fasthtml

%SPHINXBUILD% -M %1 %SOURCEDIR% %BUILDDIR% %SPHINXOPTS% %O%
set EXITCODE=%ERRORLEVEL%
goto end

:fasthtml
set SKIP_NOTEBOOK_BUILD=1
%SPHINXBUILD% -M html %SOURCEDIR% %BUILDDIR% %SPHINXOPTS% %O%
set EXITCODE=%ERRORLEVEL%
goto end

:help
%SPHINXBUILD% -M help %SOURCEDIR% %BUILDDIR% %SPHINXOPTS% %O%
set EXITCODE=%ERRORLEVEL%

:end
popd
endlocal & exit /b %EXITCODE%
