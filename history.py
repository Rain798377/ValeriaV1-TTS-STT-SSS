"""
Export conversation history to JSON.
Run: python export_history.py
Reads from history.json if the bot has been saving it,
or shows instructions to enable persistent saving.
"""
import json, os, datetime

history_file = "history.json"

if os.path.exists(history_file):
    with open(history_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    out = f"history_export_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"✅ Exported to {out}")
else:
    print("No history.json found — enable persistent saving in voice.py first.")
    print("Add this to _listen_loop after history.append(...):")
    print('  with open("history.json", "w") as f: json.dump(self.histories, f, indent=2)')