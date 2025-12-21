from hydrogram import Client, filters
from hydrogram.errors import MessageTooLong
from info import ADMINS
import sys
import traceback
import asyncio
from io import StringIO

EVAL_TIMEOUT = 5  # seconds


# ======================================================
# 🔐 SAFE BUILTINS (BLOCK DANGEROUS OPS)
# ======================================================

SAFE_BUILTINS = {
    "print": print,
    "len": len,
    "range": range,
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "dict": dict,
    "list": list,
    "set": set,
    "tuple": tuple,
    "enumerate": enumerate,
    "zip": zip,
    "min": min,
    "max": max,
    "sum": sum,
    "abs": abs,
}


# ======================================================
# 🧪 /eval COMMAND
# ======================================================

@Client.on_message(filters.command("eval") & filters.user(ADMINS))
async def eval_cmd(client, message):
    if len(message.command) < 2:
        return await message.reply(
            "❌ **Usage:**\n`/eval your_python_code`"
        )

    code = message.text.split(" ", 1)[1]

    old_stdout = sys.stdout
    old_stderr = sys.stderr
    redirected_out = sys.stdout = StringIO()
    redirected_err = sys.stderr = StringIO()

    result = "✅ Success"
    error = None

    try:
        await asyncio.wait_for(
            aexec(code, client, message),
            timeout=EVAL_TIMEOUT
        )
    except asyncio.TimeoutError:
        error = "⏱ Execution timed out (5s limit)"
    except Exception:
        error = traceback.format_exc()

    stdout = redirected_out.getvalue()
    stderr = redirected_err.getvalue()

    sys.stdout = old_stdout
    sys.stderr = old_stderr

    if error:
        output = error
    elif stderr:
        output = stderr
    elif stdout:
        output = stdout
    else:
        output = result

    final = f"<b>🧪 Eval Output</b>\n\n<code>{output}</code>"

    try:
        await message.reply(final)
    except MessageTooLong:
        with open("eval_output.txt", "w", encoding="utf-8") as f:
            f.write(output)
        await message.reply_document("eval_output.txt")
        os.remove("eval_output.txt")


# ======================================================
# ⚙️ ASYNC EXECUTOR (SANDBOXED)
# ======================================================

async def aexec(code, client, message):
    exec(
        "async def __aexec(client, message):\n"
        + "\n".join(f" {line}" for line in code.split("\n")),
        {"__builtins__": SAFE_BUILTINS},
        locals()
    )
    return await locals()["__aexec"](client, message)
