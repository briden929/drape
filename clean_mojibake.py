import re

with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V14_FINAL.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Emojis/mojibake mapping
replacements = {
    "✅": "[OK]",
    "❌": "[FAIL]",
    "⚠️": "[WARN]",
    "🛑": "[ERROR]",
    "🔄": "[RETRY]",
    "🔒": "[LOCK]",
    "🔐": "[LOCK]",
    "🔑": "[KEY]",
    "🔍": "[SEARCH]",
    "🎉": "[SUCCESS]",
    "🚀": "[LAUNCH]",
    "📱": "[MOBILE]",
    "🖥️": "[PC]",
    "📂": "[DIR]",
    "📋": "[LIST]",
    "📦": "[PKG]",
    "🔧": "[TOOL]",
    "⚙️": "[CONFIG]",
    "⏳": "[WAIT]",
    "⏱️": "[TIME]",
    "✨": "[MAGIC]",
    "🖼️": "[IMG]",
    "📸": "[PHOTO]",
    "🗑️": "[TRASH]",
    "➡️": "->",
    "•": "-",
    "—": "-",
    "‘": "'",
    "’": "'",
    "“": '"',
    "”": '"',
    "…": "...",
    "×": "x",
    "✓": "[OK]",
    "️": "", # some invisible variations
}

for k, v in replacements.items():
    text = text.replace(k, v)

# any remaining non-ascii should be stripped
text = re.sub(r'[^\x00-\x7F]+', '', text)

with open('C:\\Users\\PC\\Desktop\\FULL_QUEUE_WORKER_V14_FINAL.py', 'w', encoding='utf-8') as f:
    f.write(text)
