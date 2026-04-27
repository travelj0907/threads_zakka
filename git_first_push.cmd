@echo off
chcp 65001 >nul
cd /d "%~dp0"

REM 初回だけ: 自分の名前・メールに書き換えてから実行
git config user.name "travelj0907"
git config user.email "travelj0907@gmail.com"

git add .
git commit -m "Initial commit"
if errorlevel 1 (
  echo コミットに失敗しました（変更なし、または既にコミット済みの可能性）
)

git branch -M main

git remote remove origin 2>nul
git remote add origin https://github.com/travelj0907/threads_zakka.git

git push -u origin main
if errorlevel 1 (
  echo.
  echo push に失敗した場合: GitHub でログイン・認証（PAT など）を確認してください。
  pause
  exit /b 1
)

echo.
echo 完了
pause
