#!/usr/bin/env python3
"""
Email Sorter -- the point-and-click version.

Double-click "Start (Windows).bat" or "Start (Mac).command" to open this
window. Pick the file you downloaded from Google Takeout (the .zip is fine,
no need to unzip), click Sort, and the results open when it's done.
"""

import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import categories as C  # noqa: E402
import sort_emails  # noqa: E402

RESULTS_FOLDER = "Sorted Emails"


def open_path(path):
    """Open a file or folder with the computer's normal app for it."""
    if sys.platform == "win32":
        os.startfile(path)  # noqa: S606 -- local file chosen by the user
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


class App:
    def __init__(self, root):
        self.root = root
        self.source = None
        self.out = None
        self.events = queue.Queue()

        root.title("Email Sorter")
        root.minsize(520, 0)
        frame = ttk.Frame(root, padding=24)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="Email Sorter", font=("", 20, "bold")).pack(anchor="w")
        ttk.Label(
            frame,
            text="Sorts your emails into brand deals, licensing, press, fan mail, scams and more.\n"
                 "Everything stays on this computer -- nothing is uploaded.",
            justify="left",
        ).pack(anchor="w", pady=(4, 16))

        ttk.Label(frame, text="Step 1:  Choose the email file you downloaded from Google",
                  font=("", 12, "bold")).pack(anchor="w")
        row = ttk.Frame(frame)
        row.pack(fill="x", pady=(6, 16))
        self.choose_btn = ttk.Button(row, text="Choose file...", command=self.choose)
        self.choose_btn.pack(side="left")
        self.file_label = ttk.Label(row, text="No file chosen yet", foreground="gray")
        self.file_label.pack(side="left", padx=10)

        ttk.Label(frame, text="Step 2:  Sort", font=("", 12, "bold")).pack(anchor="w")
        self.sort_btn = ttk.Button(frame, text="Sort my emails", command=self.start, state="disabled")
        self.sort_btn.pack(anchor="w", pady=(6, 8), ipadx=12, ipady=4)

        self.bar = ttk.Progressbar(frame, mode="indeterminate", length=460)
        self.status = ttk.Label(frame, text="")
        self.status.pack(anchor="w")

        self.results = ttk.Frame(frame)
        self.results.pack(fill="both", expand=True, pady=(12, 0))

    # -- step 1 ------------------------------------------------------------
    def choose(self):
        path = filedialog.askopenfilename(
            title="Choose your Google Takeout email file",
            filetypes=[("Email export", "*.zip *.mbox"), ("All files", "*.*")],
        )
        if not path:
            return
        self.source = path
        self.file_label.config(text=os.path.basename(path), foreground="")
        self.sort_btn.config(state="normal")

    # -- step 2 ------------------------------------------------------------
    def start(self):
        self.out = os.path.join(os.path.dirname(self.source), RESULTS_FOLDER)
        for w in self.results.winfo_children():
            w.destroy()
        self.sort_btn.config(state="disabled")
        self.choose_btn.config(state="disabled")
        self.bar.pack(anchor="w", pady=(0, 6), before=self.status)
        self.bar.start(12)
        self.status.config(text="Starting... (a big inbox can take several minutes)")
        threading.Thread(target=self.work, daemon=True).start()
        self.root.after(200, self.poll)

    def work(self):
        try:
            ai = sort_emails.load_ai_results(os.path.join(self.out, "ai_results.csv"))
            counts, _ = sort_emails.run(
                self.source, self.out, ai=ai,
                progress=lambda n: self.events.put(("progress", n)),
            )
            self.events.put(("done", counts))
        except Exception as e:  # show any failure to the user instead of silently dying
            self.events.put(("error", e))

    def poll(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "progress":
                    self.status.config(text=f"Sorted {value:,} emails so far...")
                elif kind == "done":
                    self.finish(value)
                    return
                elif kind == "error":
                    self.fail(value)
                    return
        except queue.Empty:
            pass
        self.root.after(200, self.poll)

    def fail(self, err):
        self.bar.stop()
        self.bar.pack_forget()
        self.status.config(text="")
        self.sort_btn.config(state="normal")
        self.choose_btn.config(state="normal")
        if isinstance(err, PermissionError):
            msg = (f"Couldn't save results next to your email file:\n{self.out}\n\n"
                   "Move the email file to your Desktop or Documents folder and try again.")
        else:
            msg = f"Something went wrong:\n\n{err}"
        messagebox.showerror("Email Sorter", msg)

    def finish(self, counts):
        self.bar.stop()
        self.bar.pack_forget()
        self.choose_btn.config(state="normal")
        self.sort_btn.config(state="normal")
        total = sum(counts.values())
        if total == 0:
            self.status.config(text="")
            messagebox.showwarning(
                "Email Sorter",
                "No emails were found in that file.\n\nMake sure you picked the file from "
                "Google Takeout (a .zip or .mbox), and that the export included Mail.")
            return
        top = sum(counts[c] for c in C.PRIORITY_CATEGORIES)
        self.status.config(text=f"Done! Sorted {total:,} emails.  {top:,} look important.")

        table = ttk.Frame(self.results)
        table.pack(anchor="w")
        for i, cat in enumerate(c for c in C.CATEGORIES if counts[c]):
            star = "⭐ " if cat in C.PRIORITY_CATEGORIES else "     "
            ttk.Label(table, text=f"{counts[cat]:,}", width=9, anchor="e").grid(row=i, column=0, sticky="e")
            ttk.Label(table, text=f"  {star}{cat}").grid(row=i, column=1, sticky="w")

        btns = ttk.Frame(self.results)
        btns.pack(anchor="w", pady=(14, 0))
        ttk.Button(btns, text="✉ Read & reply to important emails",
                   command=lambda: open_path(os.path.join(self.out, "replies.html"))).pack(side="left", ipady=4)
        ttk.Button(btns, text="Open all results",
                   command=lambda: open_path(self.out)).pack(side="left", padx=8, ipady=4)
        ttk.Label(self.results, text=f"Saved in: {self.out}", foreground="gray").pack(anchor="w", pady=(8, 0))

        open_path(os.path.join(self.out, "replies.html"))


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
