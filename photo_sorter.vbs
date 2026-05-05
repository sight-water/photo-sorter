Set WshShell = CreateObject("WScript.Shell")
ScriptDir = Left(WScript.ScriptFullName, InStrRev(WScript.ScriptFullName, "\"))
WshShell.Run "pythonw """ & ScriptDir & "photo_sorter.py""", 0, False
