"""
Photo Sorter - キーボードショートカットで写真を素早く仕分けするツール
"""

import os
import json
import shutil
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
CONFIG_FILE = Path.home() / ".photo_sorter_config.json"

# ─────────────────────────────────────────────
# 設定の読み書き
# ─────────────────────────────────────────────

def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"rules": []}


def save_config(config: dict):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


# ─────────────────────────────────────────────
# ファイル移動ユーティリティ
# ─────────────────────────────────────────────

def safe_move(src: Path, dst_dir: Path) -> Path:
    """重複時はリネームして移動する。移動先パスを返す。"""
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / src.name
    if dst.exists():
        stem, suffix = src.stem, src.suffix
        counter = 1
        while dst.exists():
            dst = dst_dir / f"{stem}_{counter}{suffix}"
            counter += 1
    shutil.move(str(src), str(dst))
    return dst


# ─────────────────────────────────────────────
# 設定画面
# ─────────────────────────────────────────────

class SettingsDialog(tk.Toplevel):
    def __init__(self, parent, config: dict):
        super().__init__(parent)
        self.title("仕分けルールの設定")
        self.resizable(False, False)
        self.grab_set()

        self.result = None
        self.rows: list[tuple[tk.StringVar, tk.StringVar]] = []

        # ─── ヘッダー ───
        header = tk.Frame(self, bg="#2b2b2b", padx=16, pady=12)
        header.pack(fill="x")
        tk.Label(
            header, text="仕分けルールを設定",
            font=("", 14, "bold"), fg="white", bg="#2b2b2b"
        ).pack(anchor="w")
        tk.Label(
            header, text="キー（1文字）とフォルダ名を最大9個まで登録できます",
            font=("", 9), fg="#aaaaaa", bg="#2b2b2b"
        ).pack(anchor="w")

        # ─── テーブル ───
        body = tk.Frame(self, bg="#1e1e1e", padx=20, pady=16)
        body.pack(fill="both")

        tk.Label(body, text="キー", width=6, bg="#1e1e1e", fg="#888888").grid(
            row=0, column=0, padx=4)
        tk.Label(body, text="フォルダ名", width=24, bg="#1e1e1e", fg="#888888").grid(
            row=0, column=1, padx=4)

        existing = config.get("rules", [])
        for i in range(9):
            key_var = tk.StringVar()
            name_var = tk.StringVar()
            if i < len(existing):
                key_var.set(existing[i].get("key", ""))
                name_var.set(existing[i].get("name", ""))

            key_entry = tk.Entry(
                body, textvariable=key_var, width=5,
                bg="#2d2d2d", fg="white", insertbackground="white",
                relief="flat", font=("", 11), justify="center"
            )
            key_entry.grid(row=i + 1, column=0, padx=4, pady=3, ipady=4)
            key_entry.bind("<KeyRelease>", lambda e, v=key_var: self._limit_key(v))

            name_entry = tk.Entry(
                body, textvariable=name_var, width=26,
                bg="#2d2d2d", fg="white", insertbackground="white",
                relief="flat", font=("", 11)
            )
            name_entry.grid(row=i + 1, column=1, padx=4, pady=3, ipady=4)

            self.rows.append((key_var, name_var))

        # ─── ボタン ───
        footer = tk.Frame(self, bg="#1e1e1e", padx=20, pady=12)
        footer.pack(fill="x")

        tk.Button(
            footer, text="キャンセル", command=self.destroy,
            bg="#444444", fg="white", relief="flat",
            padx=16, pady=6, cursor="hand2"
        ).pack(side="right", padx=(8, 0))

        tk.Button(
            footer, text="保存して開始", command=self._save,
            bg="#0078d4", fg="white", relief="flat",
            padx=16, pady=6, cursor="hand2"
        ).pack(side="right")

        self.configure(bg="#1e1e1e")
        self.center()

    def _limit_key(self, var: tk.StringVar):
        v = var.get()
        if len(v) > 1:
            var.set(v[-1])

    def _save(self):
        rules = []
        seen_keys = set()
        for key_var, name_var in self.rows:
            k = key_var.get().strip()
            n = name_var.get().strip()
            if not k and not n:
                continue
            if not k:
                messagebox.showerror("エラー", "キーが入力されていない行があります", parent=self)
                return
            if not n:
                messagebox.showerror("エラー", "フォルダ名が入力されていない行があります", parent=self)
                return
            if k in seen_keys:
                messagebox.showerror("エラー", f"キー「{k}」が重複しています", parent=self)
                return
            seen_keys.add(k)
            rules.append({"key": k, "name": n})

        if not rules:
            messagebox.showerror("エラー", "ルールを1つ以上登録してください", parent=self)
            return

        self.result = rules
        self.destroy()

    def center(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"+{(sw - w) // 2}+{(sh - h) // 2}")


# ─────────────────────────────────────────────
# メインアプリ
# ─────────────────────────────────────────────

class PhotoSorterApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Photo Sorter")
        self.configure(bg="#1e1e1e")
        self.minsize(800, 600)

        self.config_data = load_config()
        self.source_dir: Path | None = None
        self.photos: list[Path] = []
        self.current_index: int = 0
        self.sorted_count: int = 0
        self.rules: list[dict] = []
        self._photo_image = None  # GC防止

        self._build_ui()
        self.after(100, self._start)

    # ─── UI構築 ───

    def _build_ui(self):
        # ツールバー
        toolbar = tk.Frame(self, bg="#2b2b2b", padx=10, pady=6)
        toolbar.pack(fill="x")

        self.folder_label = tk.Label(
            toolbar, text="フォルダ未選択",
            font=("", 9), fg="#aaaaaa", bg="#2b2b2b", anchor="w"
        )
        self.folder_label.pack(side="left", fill="x", expand=True)

        tk.Button(
            toolbar, text="⚙ ルール設定", command=self._open_settings,
            bg="#3a3a3a", fg="white", relief="flat", padx=10, pady=2,
            cursor="hand2", font=("", 9)
        ).pack(side="right", padx=4)

        tk.Button(
            toolbar, text="📂 フォルダ変更", command=self._change_folder,
            bg="#3a3a3a", fg="white", relief="flat", padx=10, pady=2,
            cursor="hand2", font=("", 9)
        ).pack(side="right", padx=4)

        # カウンター
        self.counter_label = tk.Label(
            self, text="",
            font=("", 10), fg="#888888", bg="#1e1e1e"
        )
        self.counter_label.pack(pady=(8, 0))

        # 画像表示エリア
        self.canvas = tk.Canvas(
            self, bg="#121212", highlightthickness=0
        )
        self.canvas.pack(fill="both", expand=True, padx=16, pady=8)

        # ファイル名
        self.filename_label = tk.Label(
            self, text="",
            font=("", 10), fg="#cccccc", bg="#1e1e1e"
        )
        self.filename_label.pack()

        # ショートカット一覧
        self.shortcut_frame = tk.Frame(self, bg="#1e1e1e")
        self.shortcut_frame.pack(pady=(4, 12))

        # ナビゲーションヒント
        nav_hint = tk.Label(
            self,
            text="← → : 前後の写真に移動（仕分けなし）　　ESC : 終了",
            font=("", 9), fg="#555555", bg="#1e1e1e"
        )
        nav_hint.pack(pady=(0, 8))

    def _update_shortcut_bar(self):
        for w in self.shortcut_frame.winfo_children():
            w.destroy()

        for rule in self.rules:
            cell = tk.Frame(self.shortcut_frame, bg="#2b2b2b", padx=8, pady=6)
            cell.pack(side="left", padx=4)
            tk.Label(
                cell,
                text=f"[{rule['key']}]",
                font=("Courier", 13, "bold"), fg="#f0c040", bg="#2b2b2b"
            ).pack(side="left")
            tk.Label(
                cell,
                text=f" {rule['name']}",
                font=("", 11), fg="white", bg="#2b2b2b"
            ).pack(side="left")

    # ─── 起動フロー ───

    def _start(self):
        # フォルダ選択
        folder = filedialog.askdirectory(title="仕分け元フォルダを選択してください")
        if not folder:
            self.destroy()
            return
        self.source_dir = Path(folder)
        self.folder_label.config(text=str(self.source_dir))

        # 設定画面
        dlg = SettingsDialog(self, self.config_data)
        self.wait_window(dlg)
        if dlg.result is None:
            self.destroy()
            return

        self.rules = dlg.result
        self.config_data["rules"] = self.rules
        save_config(self.config_data)

        self._update_shortcut_bar()
        self._load_photos()
        self._bind_keys()
        self._show_current()

    def _change_folder(self):
        folder = filedialog.askdirectory(title="仕分け元フォルダを選択")
        if not folder:
            return
        self.source_dir = Path(folder)
        self.folder_label.config(text=str(self.source_dir))
        self.sorted_count = 0
        self._load_photos()
        self._show_current()

    def _open_settings(self):
        dlg = SettingsDialog(self, self.config_data)
        self.wait_window(dlg)
        if dlg.result is not None:
            self.rules = dlg.result
            self.config_data["rules"] = self.rules
            save_config(self.config_data)
            self._update_shortcut_bar()
            self._bind_keys()

    # ─── 写真リスト ───

    def _load_photos(self):
        if not self.source_dir:
            return
        self.photos = sorted(
            p for p in self.source_dir.iterdir()
            if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
        )
        self.current_index = 0

    # ─── キーバインド ───

    def _bind_keys(self):
        self.unbind_all("<Key>")
        for rule in self.rules:
            key = rule["key"]
            name = rule["name"]
            self.bind(f"<KeyPress-{key}>", lambda e, n=name: self._sort_photo(n))
            self.bind(f"<KeyPress-{key.upper()}>", lambda e, n=name: self._sort_photo(n))
        self.bind("<Left>", lambda e: self._navigate(-1))
        self.bind("<Right>", lambda e: self._navigate(1))
        self.bind("<Escape>", lambda e: self.destroy())

    # ─── 仕分け操作 ───

    def _sort_photo(self, folder_name: str):
        if not self.photos or self.current_index >= len(self.photos):
            return
        src = self.photos[self.current_index]
        if not src.exists():
            self._next_photo()
            return

        dst_dir = self.source_dir.parent / folder_name
        safe_move(src, dst_dir)

        self.sorted_count += 1
        self.photos.pop(self.current_index)
        if self.current_index >= len(self.photos) and self.current_index > 0:
            self.current_index -= 1
        self._show_current()

    def _navigate(self, delta: int):
        if not self.photos:
            return
        self.current_index = (self.current_index + delta) % len(self.photos)
        self._show_current()

    def _next_photo(self):
        if not self.photos:
            return
        if self.current_index >= len(self.photos):
            self.current_index = max(0, len(self.photos) - 1)
        self._show_current()

    # ─── 画像表示 ───

    def _show_current(self):
        self.canvas.delete("all")
        self._photo_image = None

        if not self.photos:
            self._show_done()
            return

        # カウンター更新
        total = len(self.photos)
        idx = self.current_index + 1
        self.counter_label.config(
            text=f"{idx} / {total}  （仕分け済み: {self.sorted_count}枚）"
        )

        photo_path = self.photos[self.current_index]
        self.filename_label.config(text=photo_path.name)
        self.title(f"Photo Sorter — {photo_path.name}")

        self.update_idletasks()
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        if cw < 10 or ch < 10:
            self.after(50, self._show_current)
            return

        if PIL_AVAILABLE:
            self._show_with_pil(photo_path, cw, ch)
        else:
            self._show_with_tk(photo_path, cw, ch)

    def _show_with_pil(self, path: Path, cw: int, ch: int):
        try:
            img = Image.open(path)
            img.thumbnail((cw, ch), Image.LANCZOS)
            self._photo_image = ImageTk.PhotoImage(img)
            self.canvas.create_image(cw // 2, ch // 2, anchor="center",
                                     image=self._photo_image)
        except Exception as e:
            self.canvas.create_text(
                cw // 2, ch // 2,
                text=f"画像を読み込めませんでした\n{e}",
                fill="#888888", font=("", 12), justify="center"
            )

    def _show_with_tk(self, path: Path, cw: int, ch: int):
        suffix = path.suffix.lower()
        if suffix not in {".png", ".gif"}:
            self.canvas.create_text(
                cw // 2, ch // 2,
                text="Pillowがインストールされていないため\nJPEG/WebPを表示できません\n\npip install Pillow",
                fill="#888888", font=("", 12), justify="center"
            )
            return
        try:
            self._photo_image = tk.PhotoImage(file=str(path))
            self.canvas.create_image(cw // 2, ch // 2, anchor="center",
                                     image=self._photo_image)
        except Exception as e:
            self.canvas.create_text(
                cw // 2, ch // 2,
                text=f"画像を読み込めませんでした\n{e}",
                fill="#888888", font=("", 12), justify="center"
            )

    def _show_done(self):
        self.filename_label.config(text="")
        self.counter_label.config(text="完了")
        self.title("Photo Sorter — 完了")

        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        self.canvas.create_text(
            cw // 2, ch // 2,
            text=f"✓  {self.sorted_count}枚の仕分けが完了しました",
            fill="#4caf50", font=("", 18, "bold"), justify="center"
        )
        messagebox.showinfo(
            "完了",
            f"{self.sorted_count}枚の仕分けが完了しました。\n\nお疲れさまでした！"
        )


# ─────────────────────────────────────────────
# エントリポイント
# ─────────────────────────────────────────────

if __name__ == "__main__":
    if not PIL_AVAILABLE:
        import tkinter as _tk
        _root = _tk.Tk()
        _root.withdraw()
        _tk.messagebox.showwarning(
            "Pillowが見つかりません",
            "JPEG/WebP画像の表示にはPillowが必要です。\n\n"
            "  pip install Pillow\n\n"
            "インストール後に再起動してください。\nPNG/GIFのみの場合はこのまま続行できます。"
        )
        _root.destroy()

    app = PhotoSorterApp()
    app.mainloop()
