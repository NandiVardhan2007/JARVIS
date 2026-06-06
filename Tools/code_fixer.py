"""
Code Fixer — paste broken code + error → get AI‑powered fix via Tkinter GUI.

This is a *separate* tool from code_review_agent (which reviews files/PRs).
The Code Fixer is for interactive "I have an error" debugging sessions.
"""

import asyncio
import logging
import os
import time
from datetime import datetime

import aiohttp
from livekit.agents import function_tool

logger = logging.getLogger(__name__)

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

SUPPORTED_LANGUAGES = [
    "python", "javascript", "typescript", "java", "cpp", "c",
    "csharp", "php", "html", "css", "ruby", "go", "rust",
    "swift", "kotlin", "sql", "bash",
]


# ── Tkinter GUI ───────────────────────────────────────────────────────────────

class _CodeFixerGUI:
    """Dark‑themed Tkinter UI for the code fixer workflow."""

    # ── Input window ──────────────────────────────────────────────────────

    def show_input(self) -> tuple[str, str, str] | tuple[None, None, None]:
        """Open the input window. Returns (language, code, error) or Nones."""
        import tkinter as tk
        from tkinter import scrolledtext, messagebox

        root = tk.Tk()
        root.title("JARVIS — Code Fixer")
        root.geometry("900x680")
        root.configure(bg="#0f1923")
        root.resizable(True, True)
        root.eval("tk::PlaceWindow . center")

        result: list[str] = []

        def submit():
            lang = lang_var.get().strip()
            code = code_box.get("1.0", tk.END).strip()
            err = err_box.get("1.0", tk.END).strip()
            if not lang:
                messagebox.showerror("Missing", "Select a programming language.")
                return
            if not code:
                messagebox.showerror("Missing", "Paste your code.")
                return
            if not err:
                messagebox.showerror("Missing", "Paste the error message.")
                return
            if code.count("\n") > 500:
                messagebox.showerror("Too large", "Code must be ≤ 500 lines.")
                return
            result.extend([lang, code, err])
            root.destroy()

        # Header
        tk.Label(root, text="🔧 JARVIS Code Fixer", font=("Segoe UI", 18, "bold"),
                 fg="#60a5fa", bg="#0f1923").pack(pady=(16, 4))
        tk.Label(root, text="Paste your code and error message to get an AI fix",
                 font=("Segoe UI", 11), fg="#94a3b8", bg="#0f1923").pack(pady=(0, 12))

        # Language selector
        lang_frame = tk.Frame(root, bg="#0f1923")
        lang_frame.pack(fill="x", padx=20)
        tk.Label(lang_frame, text="Language:", font=("Segoe UI", 10, "bold"),
                 fg="#60a5fa", bg="#0f1923").pack(side="left")
        lang_var = tk.StringVar(value="python")
        tk.OptionMenu(lang_frame, lang_var, *SUPPORTED_LANGUAGES).pack(side="left", padx=8)

        # Code + Error side by side
        panes = tk.Frame(root, bg="#0f1923")
        panes.pack(fill="both", expand=True, padx=20, pady=8)

        # Code
        code_lf = tk.LabelFrame(panes, text="📝 Your Code (≤ 500 lines)",
                                font=("Segoe UI", 10, "bold"), fg="#60a5fa",
                                bg="#1e293b", relief="groove", bd=1)
        code_lf.pack(side="left", fill="both", expand=True, padx=(0, 4))
        code_box = scrolledtext.ScrolledText(code_lf, height=18, font=("Consolas", 10),
                                             bg="#0f1923", fg="#a5f3fc",
                                             insertbackground="white", relief="flat",
                                             padx=8, pady=8)
        code_box.pack(fill="both", expand=True, padx=6, pady=6)

        # Error
        err_lf = tk.LabelFrame(panes, text="❌ Error Message",
                               font=("Segoe UI", 10, "bold"), fg="#f87171",
                               bg="#1e293b", relief="groove", bd=1)
        err_lf.pack(side="right", fill="both", expand=True, padx=(4, 0))
        err_box = scrolledtext.ScrolledText(err_lf, height=18, font=("Consolas", 10),
                                            bg="#0f1923", fg="#fca5a5",
                                            insertbackground="white", relief="flat",
                                            padx=8, pady=8)
        err_box.pack(fill="both", expand=True, padx=6, pady=6)

        # Submit
        tk.Button(root, text="🔧 Fix My Code", command=submit, bg="#3b82f6", fg="white",
                  font=("Segoe UI", 13, "bold"), padx=32, pady=10, relief="flat",
                  cursor="hand2", activebackground="#2563eb").pack(pady=12)

        root.mainloop()
        if result:
            return result[0], result[1], result[2]
        return None, None, None

    # ── Result window ─────────────────────────────────────────────────────

    def show_result(self, fixed_code: str, language: str):
        import tkinter as tk
        from tkinter import scrolledtext, filedialog, messagebox

        root = tk.Tk()
        root.title(f"JARVIS — Fixed {language.upper()} Code")
        root.geometry("950x720")
        root.configure(bg="#0f1923")
        root.eval("tk::PlaceWindow . center")

        # Header
        tk.Label(root, text="✅ Code Fixed Successfully", font=("Segoe UI", 18, "bold"),
                 fg="#34d399", bg="#0f1923").pack(pady=(16, 2))
        tk.Label(root, text=f"Language: {language.upper()}  |  {fixed_code.count(chr(10)) + 1} lines",
                 font=("Segoe UI", 11), fg="#94a3b8", bg="#0f1923").pack(pady=(0, 10))

        # Code display
        code_frame = tk.Frame(root, bg="#1e293b", relief="sunken", bd=1)
        code_frame.pack(fill="both", expand=True, padx=20, pady=4)
        code_box = scrolledtext.ScrolledText(code_frame, font=("Consolas", 11),
                                             bg="#0f1923", fg="#a5f3fc",
                                             insertbackground="white", relief="flat",
                                             padx=10, pady=10, wrap="none")
        code_box.insert("1.0", fixed_code)
        code_box.config(state="disabled")
        code_box.pack(fill="both", expand=True, padx=4, pady=4)

        # Buttons
        btn_frame = tk.Frame(root, bg="#0f1923")
        btn_frame.pack(fill="x", padx=20, pady=12)

        def copy():
            root.clipboard_clear()
            root.clipboard_append(fixed_code)
            messagebox.showinfo("Copied", "Code copied to clipboard.")

        def save():
            fp = filedialog.asksaveasfilename(defaultextension=f".{language}",
                                              filetypes=[(f"{language} files", f"*.{language}"), ("All", "*.*")])
            if fp:
                with open(fp, "w", encoding="utf-8") as f:
                    f.write(fixed_code)
                messagebox.showinfo("Saved", f"Saved to {os.path.basename(fp)}")

        for text, cmd, bg in [("📋 Copy", copy, "#3b82f6"), ("💾 Save", save, "#22c55e"), ("Close", root.destroy, "#64748b")]:
            tk.Button(btn_frame, text=text, command=cmd, bg=bg, fg="white",
                      font=("Segoe UI", 11, "bold"), padx=18, pady=6, relief="flat",
                      cursor="hand2").pack(side="left", padx=6)

        root.mainloop()


# ── AI call ───────────────────────────────────────────────────────────────────

async def _call_groq(language: str, code: str, error: str) -> str:
    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        return "Error: GROQ_API_KEY is not set."

    system_msg = (
        f"You are JARVIS, an expert {language} debugger. You receive broken code and its "
        f"error message. Your job is to produce a fully corrected, runnable version.\n\n"
        "Rules:\n"
        "1. Return ONLY the corrected code — no explanations before or after.\n"
        "2. Add a brief inline comment (// FIXED: or # FIXED:) next to each line you changed.\n"
        "3. Fix ALL errors — syntax, logic, type mismatches, missing imports.\n"
        "4. Preserve the original code structure and variable names where possible.\n"
        "5. Add proper error handling if the original code was missing it.\n"
        "6. Do NOT wrap the output in markdown code fences."
    )

    prompt = (
        f"ORIGINAL {language.upper()} CODE:\n{code}\n\n"
        f"ERROR MESSAGE:\n{error}\n\n"
        "Fix this code. Return the complete corrected version."
    )

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 4000,
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(GROQ_URL, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=45)) as resp:
            if resp.status != 200:
                return f"Groq API error ({resp.status}): {(await resp.text())[:200]}"
            data = await resp.json()
            text = data["choices"][0]["message"]["content"].strip()
            # Strip markdown fences if present
            if text.startswith("```"):
                lines = text.split("\n")
                text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
            return text


# ── Tool ──────────────────────────────────────────────────────────────────────

@function_tool
async def fix_code_error() -> str:
    """
    Interactive Code Fixer — opens a GUI to paste broken code and its error
    message, then uses AI to generate a corrected version.

    Supports Python, JavaScript, Java, C++, Go, Rust, and more.
    """
    gui = _CodeFixerGUI()
    try:
        language, code, error = await asyncio.to_thread(gui.show_input)
        if not language:
            return "Code fixer cancelled — no input provided."

        logger.info(f"Fixing {language} code ({code.count(chr(10)) + 1} lines)")
        fixed = await _call_groq(language, code, error)

        await asyncio.to_thread(gui.show_result, fixed, language)
        return f"{language.capitalize()} code fixed successfully. Check the result window."

    except Exception as exc:
        logger.exception("Code fixer error")
        return f"Code fixer error: {exc}"
