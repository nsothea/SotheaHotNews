Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "d:\AI_Project\News"
WshShell.Run "d:\AI_Project\News\.venv\Scripts\python.exe -u app.py", 0, False
