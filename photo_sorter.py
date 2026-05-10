"""
Photo Sorter - キーボードショートカットで写真を素早く仕分けするツール
"""

import json
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path

try:
    from PIL import Image, ImageTk, ImageOps
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    from send2trash import send2trash
    TRASH_AVAILABLE = True
except ImportError:
    TRASH_AVAILABLE = False

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
CONFIG_FILE = Path.home() / ".photo_sorter_config.json"

# Instagram portrait post (4:5 aspect ratio)
INSTAGRAM_W = 1080
INSTAGRAM_H = 1350

# ── カラーパレット ──────────────────────────────────────
BG_BASE    = "#111111"   # メインウィンドウ背景
BG_SURFACE = "#1a1a1a"   # ツールバー・ステータスバー
BG_RAISED  = "#232323"   # カード・入力欄
BG_WIDGET  = "#2c2c2c"   # ボタン通常時
BG_HOVER   = "#383838"   # ボタンホバー時
BORDER_CLR = "#2e2e2e"   # 区切り線・ボーダー
ACCENT     = "#3b82f6"   # 青アクセント
ACCENT_HOV = "#60a5fa"   # 青アクセント（ホバー）
SUCCESS    = "#22c55e"   # 緑（成功）
AMBER      = "#f59e0b"   # 黄（キーバッジ）
T_PRIMARY  = "#f0f0f0"   # 主テキスト
T_SECONDARY= "#7a7a7a"   # 副テキスト
T_MUTED    = "#404040"   # 薄テキスト
CANVAS_BG  = "#090909"   # 画像表示エリア背景


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
# UIヘルパー
# ─────────────────────────────────────────────

def _make_btn(parent, text: str, command, accent: bool = False, **kw) -> tk.Label:
    """ホバーエフェクト付きフラットボタン（Label実装）"""
    n_bg = ACCENT if accent else BG_WIDGET
    h_bg = ACCENT_HOV if accent else BG_HOVER
    btn = tk.Label(
        parent, text=text, cursor="hand2",
        bg=n_bg, fg=T_PRIMARY, font=("", 9),
        padx=12, pady=6, **kw
    )
    btn.bind("<Enter>",    lambda e: btn.config(bg=h_bg))
    btn.bind("<Leave>",    lambda e: btn.config(bg=n_bg))
    btn.bind("<Button-1>", lambda e: command())
    return btn


def _separator(parent, vertical: bool = False) -> tk.Frame:
    """1px区切り線"""
    if vertical:
        return tk.Frame(parent, width=1, bg=BORDER_CLR)
    return tk.Frame(parent, height=1, bg=BORDER_CLR)


# ─────────────────────────────────────────────
# 設定画面
# ─────────────────────────────────────────────

class SettingsDialog(tk.Toplevel):
    def __init__(self, parent, config: dict):
        super().__init__(parent)
        self.title("仕分けルールの設定")
        self.resizable(False, False)
        self.configure(bg=BG_BASE)
        self.grab_set()

        self.result = None
        self.rows: list[tuple[tk.StringVar, tk.StringVar]] = []

        # ── ヘッダー ──
        hdr = tk.Frame(self, bg=BG_SURFACE, padx=24, pady=18)
        hdr.pack(fill="x")
        tk.Label(
            hdr, text="仕分けルール設定",
            font=("", 15, "bold"), fg=T_PRIMARY, bg=BG_SURFACE
        ).pack(anchor="w")
        tk.Label(
            hdr, text="キー（1文字） → 移動先フォルダ名を最大9個まで登録",
            font=("", 9), fg=T_SECONDARY, bg=BG_SURFACE
        ).pack(anchor="w", pady=(3, 0))

        _separator(self).pack(fill="x")

        # ── テーブル ──
        body = tk.Frame(self, bg=BG_BASE, padx=24, pady=18)
        body.pack(fill="both")

        tk.Label(body, text="キー", width=7, anchor="center",
                 font=("", 9), fg=T_SECONDARY, bg=BG_BASE).grid(
            row=0, column=0, padx=(0, 10), pady=(0, 6))
        tk.Label(body, text="フォルダ名", anchor="w",
                 font=("", 9), fg=T_SECONDARY, bg=BG_BASE).grid(
            row=0, column=1, sticky="w", pady=(0, 6))

        existing = config.get("rules", [])
        for i in range(9):
            key_var  = tk.StringVar()
            name_var = tk.StringVar()
            if i < len(existing):
                key_var.set(existing[i].get("key", ""))
                name_var.set(existing[i].get("name", ""))

            key_e = tk.Entry(
                body, textvariable=key_var, width=5,
                bg=BG_RAISED, fg=T_PRIMARY, insertbackground=T_PRIMARY,
                relief="flat", font=("Courier", 12, "bold"), justify="center",
                highlightthickness=1,
                highlightcolor=ACCENT, highlightbackground=BORDER_CLR
            )
            key_e.grid(row=i + 1, column=0, padx=(0, 10), pady=3, ipady=7)
            key_e.bind("<KeyRelease>", lambda e, v=key_var: self._limit_key(v))

            name_e = tk.Entry(
                body, textvariable=name_var, width=28,
                bg=BG_RAISED, fg=T_PRIMARY, insertbackground=T_PRIMARY,
                relief="flat", font=("", 11),
                highlightthickness=1,
                highlightcolor=ACCENT, highlightbackground=BORDER_CLR
            )
            name_e.grid(row=i + 1, column=1, pady=3, ipady=7)

            self.rows.append((key_var, name_var))

        # ── フッター ──
        _separator(self).pack(fill="x")
        footer = tk.Frame(self, bg=BG_SURFACE, padx=24, pady=14)
        footer.pack(fill="x")

        _make_btn(footer, "キャンセル", self.destroy).pack(side="right", padx=(8, 0))
        _make_btn(footer, "保存して開始", self._save, accent=True).pack(side="right")

        self.configure(bg=BG_BASE)
        self._center()

    def _limit_key(self, var: tk.StringVar):
        v = var.get()
        if len(v) > 1:
            var.set(v[-1])

    def _save(self):
        rules, seen = [], set()
        for kv, nv in self.rows:
            k, n = kv.get().strip(), nv.get().strip()
            if not k and not n:
                continue
            if not k:
                messagebox.showerror("エラー", "キーが空の行があります", parent=self)
                return
            if not n:
                messagebox.showerror("エラー", "フォルダ名が空の行があります", parent=self)
                return
            if k in seen:
                messagebox.showerror("エラー", f"キー「{k}」が重複しています", parent=self)
                return
            seen.add(k)
            rules.append({"key": k, "name": n})

        if not rules:
            messagebox.showerror("エラー", "ルールを1つ以上登録してください", parent=self)
            return

        self.result = rules
        self.destroy()

    def _center(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"+{(sw - w) // 2}+{(sh - h) // 2}")


# ─────────────────────────────────────────────
# Instagram用リサイズ ダイアログ
# ─────────────────────────────────────────────

class ResizeProgressDialog(tk.Toplevel):
    """Instagram portrait サイズへのバッチリサイズ進捗ダイアログ"""

    def __init__(self, parent, photos: list, out_dir: Path):
        super().__init__(parent)
        self.title("Instagram用リサイズ")
        self.resizable(False, False)
        self.configure(bg=BG_BASE)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", lambda: None)  # 処理中は閉じない

        self.photos = photos
        self.out_dir = out_dir
        self.current = 0
        self.done_count = 0
        self.error_count = 0
        self.total = len(photos)

        # ── ヘッダー ──
        hdr = tk.Frame(self, bg=BG_SURFACE, padx=24, pady=18)
        hdr.pack(fill="x")
        tk.Label(
            hdr, text="Instagram用にリサイズ中...",
            font=("", 15, "bold"), fg=T_PRIMARY, bg=BG_SURFACE
        ).pack(anchor="w")
        tk.Label(
            hdr, text=f"{INSTAGRAM_W} × {INSTAGRAM_H} px　元の比率を維持・余白は黒で埋める",
            font=("", 9), fg=T_SECONDARY, bg=BG_SURFACE
        ).pack(anchor="w", pady=(3, 0))

        _separator(self).pack(fill="x")

        # ── 本体 ──
        body = tk.Frame(self, bg=BG_BASE, padx=24, pady=20)
        body.pack(fill="both")

        self._progress_label = tk.Label(
            body, text=f"0 / {self.total}",
            font=("", 11), fg=T_PRIMARY, bg=BG_BASE
        )
        self._progress_label.pack()

        self._file_label = tk.Label(
            body, text="",
            font=("", 9), fg=T_SECONDARY, bg=BG_BASE, width=44, anchor="center"
        )
        self._file_label.pack(pady=(4, 12))

        self._prog_canvas = tk.Canvas(
            body, height=6, bg=BG_RAISED, highlightthickness=0
        )
        self._prog_canvas.pack(fill="x")

        # ── フッター ──
        _separator(self).pack(fill="x")
        footer = tk.Frame(self, bg=BG_SURFACE, padx=24, pady=12)
        footer.pack(fill="x")
        tk.Label(
            footer, text=f"保存先: {out_dir}",
            font=("", 8), fg=T_SECONDARY, bg=BG_SURFACE
        ).pack(anchor="w")

        self._center()
        self.after(50, self._process_next)

    def _process_next(self):
        if self.current >= self.total:
            self.destroy()
            return

        photo = self.photos[self.current]
        self._file_label.config(text=photo.name)

        try:
            self._resize_one(photo)
            self.done_count += 1
        except Exception:
            self.error_count += 1

        self.current += 1

        ratio = self.current / self.total
        self._progress_label.config(text=f"{self.current} / {self.total}")
        self._prog_canvas.update_idletasks()
        pw = self._prog_canvas.winfo_width()
        self._prog_canvas.delete("all")
        self._prog_canvas.create_rectangle(
            0, 0, int(pw * ratio), 6, fill=ACCENT, outline=""
        )

        self.after(5, self._process_next)

    def _resize_one(self, path: Path):
        img = Image.open(path)
        img = ImageOps.exif_transpose(img)

        # アニメーションGIFは最初のフレームのみ使用
        if getattr(img, "is_animated", False):
            img.seek(0)

        # RGB に統一（透明チャンネルは黒背景に合成）
        if img.mode != "RGB":
            base = Image.new("RGB", img.size, (0, 0, 0))
            if img.mode == "RGBA":
                base.paste(img, mask=img.split()[3])
            else:
                base.paste(img.convert("RGB"))
            img = base

        iw, ih = img.size
        scale = min(INSTAGRAM_W / iw, INSTAGRAM_H / ih)
        new_w = round(iw * scale)
        new_h = round(ih * scale)

        img_resized = img.resize((new_w, new_h), Image.LANCZOS)

        canvas = Image.new("RGB", (INSTAGRAM_W, INSTAGRAM_H), (0, 0, 0))
        x = (INSTAGRAM_W - new_w) // 2
        y = (INSTAGRAM_H - new_h) // 2
        canvas.paste(img_resized, (x, y))

        out_path = self.out_dir / (path.stem + ".jpg")
        if out_path.exists():
            counter = 1
            while out_path.exists():
                out_path = self.out_dir / f"{path.stem}_{counter}.jpg"
                counter += 1

        # quality=95, subsampling=0 で高画質保存
        canvas.save(out_path, "JPEG", quality=95, subsampling=0)

    def _center(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"+{(sw - w) // 2}+{(sh - h) // 2}")


# ─────────────────────────────────────────────
# メインアプリ
# ─────────────────────────────────────────────

class PhotoSorterApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Photo Sorter")
        self.configure(bg=BG_BASE)
        self.minsize(860, 640)

        self.config_data = load_config()
        self.source_dir: Path | None = None
        self.photos: list[Path] = []
        self.current_index: int = 0
        self.sorted_count: int = 0
        self._total_original: int = 0
        self.rules: list[dict] = []
        self._undo_stack: list[dict] = []  # {"src": Path, "dst": Path, "index": int}
        self._photo_image = None
        self._toast_window: tk.Toplevel | None = None
        self._toast_after_id = None

        # モザイク機能
        self._mosaic_mode = False
        self._mosaic_start: tuple[int, int] | None = None
        self._mosaic_rect = None  # canvas上の選択矩形ID
        self._mosaic_strength = tk.IntVar(value=20)  # ブロックサイズ: 10, 20, 40
        self._display_info: tuple | None = None  # (scale, offset_x, offset_y, orig_w, orig_h)
        self._mosaic_btn = None
        self._mosaic_bar: tk.Frame | None = None

        # トリミング機能
        self._crop_mode = False
        self._crop_start: tuple[int, int] | None = None
        self._crop_rect = None  # canvas上の選択矩形ID
        self._crop_btn = None
        self._crop_bar: tk.Frame | None = None

        # 評価・フラグ
        self._ratings: dict = self.config_data.get("ratings", {})
        self._star_labels: list[tk.Label] = []
        self._flag_label: tk.Label | None = None

        # サムネイル一覧
        self._grid_mode = False
        self._grid_btn = None
        self._grid_frame: tk.Frame | None = None
        self._grid_canvas: tk.Canvas | None = None
        self._thumb_images: list = []
        self._thumb_size = 150
        self._canvas_bottom_sep: tk.Frame | None = None

        self._build_ui()
        self.after(100, self._start)

    # ── UI構築 ────────────────────────────────

    def _build_ui(self):
        # ── ツールバー ──────────────────────────
        toolbar = tk.Frame(self, bg=BG_SURFACE, padx=16, pady=11)
        toolbar.pack(fill="x")

        tk.Label(
            toolbar, text="◈  Photo Sorter",
            font=("", 12, "bold"), fg=T_PRIMARY, bg=BG_SURFACE
        ).pack(side="left")

        self.folder_label = tk.Label(
            toolbar, text="フォルダ未選択",
            font=("", 9), fg=T_SECONDARY, bg=BG_SURFACE, anchor="w"
        )
        self.folder_label.pack(side="left", padx=(14, 0), fill="x", expand=True)

        _make_btn(toolbar, "⚙  ルール設定", self._open_settings).pack(
            side="right", padx=(6, 0))
        _make_btn(toolbar, "📂  フォルダ変更", self._change_folder).pack(
            side="right", padx=(6, 0))
        _make_btn(toolbar, "📸  Instagramリサイズ", self._resize_for_instagram).pack(
            side="right", padx=(6, 0))
        self._mosaic_btn = _make_btn(toolbar, "🔲  モザイク", self._toggle_mosaic_mode)
        self._mosaic_btn.pack(side="right", padx=(6, 0))
        self._crop_btn = _make_btn(toolbar, "✂  トリミング", self._toggle_crop_mode)
        self._crop_btn.pack(side="right", padx=(6, 0))
        _separator(toolbar, vertical=True).pack(side="right", fill="y", pady=4, padx=4)
        _make_btn(toolbar, "↺", lambda: self._rotate_photo(90), padx=8).pack(side="right", padx=(2, 0))
        _make_btn(toolbar, "↻", lambda: self._rotate_photo(-90), padx=8).pack(side="right", padx=(2, 0))
        _make_btn(toolbar, "↔", self._flip_photo, padx=8).pack(side="right", padx=(2, 0))
        _separator(toolbar, vertical=True).pack(side="right", fill="y", pady=4, padx=4)
        self._grid_btn = _make_btn(toolbar, "⊞  グリッド", self._toggle_grid_mode)
        self._grid_btn.pack(side="right", padx=(2, 0))
        _make_btn(toolbar, "🗑  削除", self._delete_photo).pack(side="right", padx=(2, 6))

        # ── プログレスバー（3px線）──────────────
        _separator(self).pack(fill="x")
        self._prog_canvas = tk.Canvas(
            self, height=3, bg=BG_SURFACE, highlightthickness=0
        )
        self._prog_canvas.pack(fill="x")

        # ── モザイクコントロールバー（モザイクモード時のみ表示）──
        self._mosaic_bar = tk.Frame(self, bg=BG_SURFACE, padx=16, pady=8)
        tk.Label(
            self._mosaic_bar, text="🔲  モザイクモード：ドラッグして範囲を選択",
            font=("", 9, "bold"), fg=T_PRIMARY, bg=BG_SURFACE
        ).pack(side="left", padx=(0, 20))
        tk.Label(
            self._mosaic_bar, text="粗さ：",
            font=("", 9), fg=T_SECONDARY, bg=BG_SURFACE
        ).pack(side="left")
        for label, val in [("細かい", 10), ("普通", 20), ("粗い", 40)]:
            tk.Radiobutton(
                self._mosaic_bar, text=label, variable=self._mosaic_strength, value=val,
                font=("", 9), fg=T_PRIMARY, bg=BG_SURFACE,
                activebackground=BG_SURFACE, activeforeground=T_PRIMARY,
                selectcolor=BG_RAISED, relief="flat", cursor="hand2"
            ).pack(side="left", padx=(0, 8))
        tk.Label(
            self._mosaic_bar, text="（クリックで解除）",
            font=("", 8), fg=T_MUTED, bg=BG_SURFACE
        ).pack(side="left", padx=(12, 0))

        # ── トリミングコントロールバー（トリミングモード時のみ表示）──
        self._crop_bar = tk.Frame(self, bg="#1a2a1a", padx=16, pady=8)
        tk.Label(
            self._crop_bar, text="✂  トリミングモード：ドラッグして範囲を選択",
            font=("", 9, "bold"), fg=T_PRIMARY, bg="#1a2a1a"
        ).pack(side="left", padx=(0, 20))
        tk.Label(
            self._crop_bar, text="範囲を決定すると確認ダイアログが表示されます",
            font=("", 9), fg=T_SECONDARY, bg="#1a2a1a"
        ).pack(side="left")
        tk.Label(
            self._crop_bar, text="（クリックで解除）",
            font=("", 8), fg=T_MUTED, bg="#1a2a1a"
        ).pack(side="left", padx=(12, 0))

        # ── 画像キャンバス ──────────────────────
        self.canvas = tk.Canvas(self, bg=CANVAS_BG, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self._canvas_bottom_sep = _separator(self)
        self._canvas_bottom_sep.pack(fill="x")

        # ── ステータスバー（ファイル名・カウンタ）─
        status = tk.Frame(self, bg=BG_SURFACE, pady=10)
        status.pack(fill="x")

        self.filename_label = tk.Label(
            status, text="",
            font=("", 11, "bold"), fg=T_PRIMARY, bg=BG_SURFACE
        )
        self.filename_label.pack()

        self.counter_label = tk.Label(
            status, text="",
            font=("", 9), fg=T_SECONDARY, bg=BG_SURFACE
        )
        self.counter_label.pack(pady=(2, 0))

        # ── 評価・フラグバー ────────────────────
        rating_frame = tk.Frame(status, bg=BG_SURFACE)
        rating_frame.pack(pady=(6, 0))
        self._star_labels = []
        for i in range(1, 6):
            lbl = tk.Label(
                rating_frame, text="☆", font=("", 16), fg=T_MUTED,
                bg=BG_SURFACE, cursor="hand2", padx=1
            )
            lbl.pack(side="left")
            lbl.bind("<Button-1>", lambda e, s=i: self._set_rating(s))
            self._star_labels.append(lbl)
        tk.Label(rating_frame, text="  ", bg=BG_SURFACE).pack(side="left")
        self._flag_label = tk.Label(
            rating_frame, text="🏳", font=("", 13), fg=T_MUTED,
            bg=BG_SURFACE, cursor="hand2"
        )
        self._flag_label.pack(side="left", padx=(4, 0))
        self._flag_label.bind("<Button-1>", lambda e: self._toggle_flag())

        # ── ショートカットバー ──────────────────
        _separator(self).pack(fill="x")
        self.shortcut_frame = tk.Frame(self, bg=BG_BASE, pady=10)
        self.shortcut_frame.pack()

        # ── ナビゲーションヒント ────────────────
        _separator(self).pack(fill="x")
        tk.Label(
            self,
            text="←  →  前後に移動　　Ctrl+Z  元に戻す　　Delete  削除　　ESC  終了",
            font=("", 9), fg=T_MUTED, bg=BG_BASE, pady=7
        ).pack()

    def _update_shortcut_bar(self):
        for w in self.shortcut_frame.winfo_children():
            w.destroy()

        for rule in self.rules:
            # ボーダー枠（外枠 1px 効果）
            outer = tk.Frame(self.shortcut_frame, bg=BORDER_CLR)
            outer.pack(side="left", padx=5)
            inner = tk.Frame(outer, bg=BG_RAISED, padx=14, pady=8)
            inner.pack(padx=1, pady=1)

            # キーラベル（黄）
            tk.Label(
                inner, text=rule["key"].upper(),
                font=("Courier", 13, "bold"), fg=AMBER, bg=BG_RAISED,
                width=2, anchor="center"
            ).pack(side="left")

            # フォルダ名
            tk.Label(
                inner, text=f"  {rule['name']}",
                font=("", 10), fg=T_PRIMARY, bg=BG_RAISED
            ).pack(side="left")

    def _update_progress(self):
        if self._total_original == 0:
            return
        self._prog_canvas.update_idletasks()
        w = self._prog_canvas.winfo_width()
        if w < 2:
            return
        ratio = self.sorted_count / self._total_original
        self._prog_canvas.delete("all")
        self._prog_canvas.create_rectangle(
            0, 0, int(w * ratio), 3, fill=ACCENT, outline=""
        )

    # ── 起動フロー ────────────────────────────

    def _start(self):
        folder = filedialog.askdirectory(title="仕分け元フォルダを選択してください")
        if not folder:
            self.destroy()
            return
        self.source_dir = Path(folder)
        self.folder_label.config(text=str(self.source_dir))

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
        self._update_progress()
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

    def _resize_for_instagram(self):
        if not PIL_AVAILABLE:
            messagebox.showerror(
                "Pillowが必要です",
                "この機能にはPillowが必要です。\n\n  pip install Pillow\n\nインストール後に再起動してください。"
            )
            return

        folder = filedialog.askdirectory(title="リサイズする写真のフォルダを選択してください")
        if not folder:
            return
        src_dir = Path(folder)

        photos = sorted(
            p for p in src_dir.iterdir()
            if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
        )

        if not photos:
            messagebox.showinfo("対象なし", "対応する画像ファイルが見つかりませんでした。")
            return

        out_dir = src_dir / "instagram"
        out_dir.mkdir(parents=True, exist_ok=True)

        dlg = ResizeProgressDialog(self, photos, out_dir)
        self.wait_window(dlg)

        if dlg.done_count > 0:
            msg = f"{dlg.done_count}枚のリサイズが完了しました。\n\n保存先: {out_dir}"
            if dlg.error_count > 0:
                msg += f"\n\n※ {dlg.error_count}枚の処理に失敗しました"
            messagebox.showinfo("完了", msg)
        else:
            messagebox.showwarning("エラー", "リサイズできたファイルがありませんでした。")

    # ── 写真リスト ────────────────────────────

    def _load_photos(self):
        if not self.source_dir:
            return
        self.photos = sorted(
            p for p in self.source_dir.iterdir()
            if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
        )
        self.current_index = 0
        self._total_original = len(self.photos)
        self._undo_stack.clear()

    # ── キーバインド ──────────────────────────

    def _bind_keys(self):
        self.unbind_all("<Key>")
        for rule in self.rules:
            key = rule["key"]
            name = rule["name"]
            self.bind(f"<KeyPress-{key}>",        lambda e, n=name: self._sort_photo(n))
            self.bind(f"<KeyPress-{key.upper()}>", lambda e, n=name: self._sort_photo(n))
        self.bind("<Left>",      lambda e: self._navigate(-1))
        self.bind("<Right>",     lambda e: self._navigate(1))
        self.bind("<Control-z>", lambda e: self._undo_sort())
        self.bind("<Control-Z>", lambda e: self._undo_sort())
        self.bind("<Delete>",    lambda e: self._delete_photo())
        self.bind("<Return>",    lambda e: self._grid_mode and self._grid_click(self.current_index))
        self.bind("<Escape>",    lambda e: self.destroy())

    # ── 仕分け操作 ────────────────────────────

    def _sort_photo(self, folder_name: str):
        if not self.photos or self.current_index >= len(self.photos):
            return
        src = self.photos[self.current_index]
        if not src.exists():
            self._next_photo()
            return

        dst_dir = self.source_dir / folder_name
        dst = safe_move(src, dst_dir)

        # 評価データを移動先パスに引き継ぐ
        src_key = str(src)
        if src_key in self._ratings:
            self._ratings[str(dst)] = self._ratings.pop(src_key)

        self._undo_stack.append({"src": src, "dst": dst, "index": self.current_index})
        self.sorted_count += 1
        self.photos.pop(self.current_index)
        if self.current_index >= len(self.photos) and self.current_index > 0:
            self.current_index -= 1

        self._show_toast(f"→  {folder_name}")
        self._update_progress()
        self._show_current()

    def _undo_sort(self):
        if not self._undo_stack:
            return
        entry = self._undo_stack.pop()
        src: Path = entry["src"]
        dst: Path = entry["dst"]
        idx: int  = entry["index"]

        if not dst.exists():
            self._undo_stack.clear()
            messagebox.showwarning("元に戻せません", "移動先のファイルが見つかりません。\n外部で変更された可能性があります。")
            return

        shutil.move(str(dst), str(src))

        # 評価データを元のパスに戻す
        dst_key = str(dst)
        if dst_key in self._ratings:
            self._ratings[str(src)] = self._ratings.pop(dst_key)

        self.photos.insert(idx, src)
        self.current_index = idx
        self.sorted_count -= 1
        self._update_progress()
        self._show_toast_undo(f"↩  {src.name}")
        self._show_current()

    def _show_toast_undo(self, message: str):
        """アンドゥ専用トースト（オレンジ色）"""
        if self._toast_after_id is not None:
            self.after_cancel(self._toast_after_id)
            self._toast_after_id = None
        if self._toast_window is not None:
            try:
                self._toast_window.destroy()
            except tk.TclError:
                pass

        toast = tk.Toplevel(self)
        toast.overrideredirect(True)
        toast.attributes("-topmost", True)

        tk.Label(
            toast, text=message,
            font=("", 12, "bold"), fg="white", bg="#d97706",
            padx=18, pady=10
        ).pack()

        self.update_idletasks()
        mw = self.winfo_x() + self.winfo_width()
        mh = self.winfo_y() + self.winfo_height()
        toast.update_idletasks()
        tw, th = toast.winfo_width(), toast.winfo_height()
        toast.geometry(f"+{mw - tw - 24}+{mh - th - 48}")

        self._toast_window = toast
        self._toast_after_id = self.after(1800, self._dismiss_toast)

    def _show_toast(self, message: str):
        if self._toast_after_id is not None:
            self.after_cancel(self._toast_after_id)
            self._toast_after_id = None
        if self._toast_window is not None:
            try:
                self._toast_window.destroy()
            except tk.TclError:
                pass

        toast = tk.Toplevel(self)
        toast.overrideredirect(True)
        toast.attributes("-topmost", True)

        tk.Label(
            toast, text=message,
            font=("", 12, "bold"), fg="white", bg=SUCCESS,
            padx=18, pady=10
        ).pack()

        self.update_idletasks()
        mw = self.winfo_x() + self.winfo_width()
        mh = self.winfo_y() + self.winfo_height()
        toast.update_idletasks()
        tw, th = toast.winfo_width(), toast.winfo_height()
        toast.geometry(f"+{mw - tw - 24}+{mh - th - 48}")

        self._toast_window = toast
        self._toast_after_id = self.after(1800, self._dismiss_toast)

    def _dismiss_toast(self):
        self._toast_after_id = None
        if self._toast_window is not None:
            try:
                self._toast_window.destroy()
            except tk.TclError:
                pass
            self._toast_window = None

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

    # ── 画像表示 ──────────────────────────────

    def _show_current(self):
        if not self.photos:
            if self._grid_mode:
                self._exit_grid_mode()
            self._show_done()
            return

        total = len(self.photos)
        idx = self.current_index + 1
        self.counter_label.config(
            text=f"{idx} / {total}　　仕分け済み {self.sorted_count} 枚"
        )
        photo_path = self.photos[self.current_index]
        self.filename_label.config(text=photo_path.name)
        self.title(f"Photo Sorter — {photo_path.name}")
        self._update_rating_bar()

        if self._grid_mode:
            self._build_grid()
            return

        self.canvas.delete("all")
        self._photo_image = None
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
            img = ImageOps.exif_transpose(img)   # EXIF向き補正（縦撮り写真を正しく表示）
            orig_w, orig_h = img.size
            img.thumbnail((cw, ch), Image.LANCZOS)
            disp_w, disp_h = img.size
            offset_x = (cw - disp_w) // 2
            offset_y = (ch - disp_h) // 2
            # 表示スケール（canvas座標→元画像座標の変換係数）
            scale = orig_w / disp_w
            self._display_info = (scale, offset_x, offset_y, orig_w, orig_h)
            self._photo_image = ImageTk.PhotoImage(img)
            self.canvas.create_image(
                cw // 2, ch // 2, anchor="center", image=self._photo_image
            )
        except Exception as e:
            self._display_info = None
            self.canvas.create_text(
                cw // 2, ch // 2,
                text=f"画像を読み込めませんでした\n{e}",
                fill=T_SECONDARY, font=("", 12), justify="center"
            )

    def _show_with_tk(self, path: Path, cw: int, ch: int):
        suffix = path.suffix.lower()
        if suffix not in {".png", ".gif"}:
            self.canvas.create_text(
                cw // 2, ch // 2,
                text="Pillowがインストールされていないため\n"
                     "JPEG/WebPを表示できません\n\npip install Pillow",
                fill=T_SECONDARY, font=("", 12), justify="center"
            )
            return
        try:
            self._photo_image = tk.PhotoImage(file=str(path))
            self.canvas.create_image(
                cw // 2, ch // 2, anchor="center", image=self._photo_image
            )
        except Exception as e:
            self.canvas.create_text(
                cw // 2, ch // 2,
                text=f"画像を読み込めませんでした\n{e}",
                fill=T_SECONDARY, font=("", 12), justify="center"
            )

    # ── 共通ユーティリティ ────────────────────────────────────

    def _save_image(self, img: "Image.Image", path: Path):
        """フォーマットを維持して画像を上書き保存"""
        suffix = path.suffix.lower()
        if suffix in {".jpg", ".jpeg"}:
            img.save(path, "JPEG", quality=95, subsampling=0)
        elif suffix == ".png":
            img.save(path, "PNG")
        elif suffix == ".webp":
            img.save(path, "WEBP", quality=95)
        else:
            img.save(path)

    # ── 回転・反転 ────────────────────────────────────────────

    def _rotate_photo(self, degrees: int):
        """degrees: 90=右回転, -90=左回転"""
        if not PIL_AVAILABLE or not self.photos:
            return
        photo_path = self.photos[self.current_index]
        try:
            img = Image.open(photo_path)
            img = ImageOps.exif_transpose(img)
            rotated = img.rotate(-degrees, expand=True)
            self._save_image(rotated, photo_path)
            self._show_current()
        except Exception as e:
            messagebox.showerror("エラー", f"回転に失敗しました:\n{e}")

    def _flip_photo(self):
        """水平反転"""
        if not PIL_AVAILABLE or not self.photos:
            return
        photo_path = self.photos[self.current_index]
        try:
            img = Image.open(photo_path)
            img = ImageOps.exif_transpose(img)
            flipped = img.transpose(Image.FLIP_LEFT_RIGHT)
            self._save_image(flipped, photo_path)
            self._show_current()
        except Exception as e:
            messagebox.showerror("エラー", f"反転に失敗しました:\n{e}")

    # ── 削除（ゴミ箱）────────────────────────────────────────

    def _delete_photo(self):
        if not self.photos or self.current_index >= len(self.photos):
            return
        photo_path = self.photos[self.current_index]
        confirmed = messagebox.askyesno(
            "削除の確認",
            f"このファイルをゴミ箱に送りますか？\n\n  {photo_path.name}",
            icon="warning"
        )
        if not confirmed:
            return
        try:
            if TRASH_AVAILABLE:
                send2trash(str(photo_path))
            else:
                safe_move(photo_path, self.source_dir / "_deleted")

            self.photos.pop(self.current_index)
            if self.current_index >= len(self.photos) and self.current_index > 0:
                self.current_index -= 1

            self._show_toast("🗑  ゴミ箱に送りました")
            self._update_progress()
            self._show_current()
        except Exception as e:
            messagebox.showerror("エラー", f"削除に失敗しました:\n{e}")

    # ── サムネイル一覧 ────────────────────────────────────────

    def _toggle_grid_mode(self):
        if not PIL_AVAILABLE:
            messagebox.showerror(
                "Pillowが必要です",
                "この機能にはPillowが必要です。\n\n  pip install Pillow\n\nインストール後に再起動してください。"
            )
            return
        if self._grid_mode:
            self._exit_grid_mode()
        else:
            self._enter_grid_mode()

    def _enter_grid_mode(self):
        if self._mosaic_mode:
            self._exit_mosaic_mode()
        if self._crop_mode:
            self._exit_crop_mode()

        if self._grid_frame is None:
            self._grid_frame = tk.Frame(self, bg=CANVAS_BG)
            inner = tk.Frame(self._grid_frame, bg=CANVAS_BG)
            inner.pack(fill="both", expand=True)
            sb = tk.Scrollbar(inner, orient="vertical", bg=BG_RAISED, troughcolor=BG_BASE)
            sb.pack(side="right", fill="y")
            self._grid_canvas = tk.Canvas(
                inner, bg=CANVAS_BG, highlightthickness=0, yscrollcommand=sb.set
            )
            self._grid_canvas.pack(side="left", fill="both", expand=True)
            sb.config(command=self._grid_canvas.yview)
            self._grid_canvas.bind(
                "<MouseWheel>",
                lambda e: self._grid_canvas.yview_scroll(-1 * (e.delta // 120), "units")
            )

        self._grid_mode = True
        self._grid_btn.config(bg=ACCENT, text="⊞  1枚表示")
        self._grid_btn.bind("<Enter>", lambda e: self._grid_btn.config(bg=ACCENT_HOV))
        self._grid_btn.bind("<Leave>", lambda e: self._grid_btn.config(bg=ACCENT))
        self.canvas.pack_forget()
        self._grid_frame.pack(fill="both", expand=True, before=self._canvas_bottom_sep)
        self.after(50, self._build_grid)

    def _exit_grid_mode(self):
        self._grid_mode = False
        self._grid_btn.config(bg=BG_WIDGET, text="⊞  グリッド")
        self._grid_btn.bind("<Enter>", lambda e: self._grid_btn.config(bg=BG_HOVER))
        self._grid_btn.bind("<Leave>", lambda e: self._grid_btn.config(bg=BG_WIDGET))
        if self._grid_frame:
            self._grid_frame.pack_forget()
        self.canvas.pack(fill="both", expand=True, before=self._canvas_bottom_sep)
        self._show_current()

    def _build_grid(self):
        if not self._grid_canvas or not self._grid_mode:
            return

        self._grid_canvas.delete("all")
        self._thumb_images.clear()

        if not self.photos:
            return

        self._grid_canvas.update_idletasks()
        gw = max(self._grid_canvas.winfo_width(), 600)

        thumb = self._thumb_size
        pad = 12
        cell_h = thumb + 40
        cols = max(2, (gw - pad) // (thumb + pad))

        for i, photo_path in enumerate(self.photos):
            col = i % cols
            row = i // cols
            x = pad + col * (thumb + pad)
            y = pad + row * (cell_h + pad)
            is_current = (i == self.current_index)

            tag = f"cell_{i}"
            self._grid_canvas.create_rectangle(
                x - 3, y - 3, x + thumb + 3, y + cell_h + 3,
                fill="#1e3a5f" if is_current else BG_RAISED,
                outline=ACCENT if is_current else BORDER_CLR,
                width=2 if is_current else 1,
                tags=(tag,)
            )

            try:
                img = Image.open(photo_path)
                img = ImageOps.exif_transpose(img)
                img.thumbnail((thumb, thumb), Image.LANCZOS)
                iw, ih = img.size
                ix = x + (thumb - iw) // 2
                iy = y + (thumb - ih) // 2
                tk_img = ImageTk.PhotoImage(img)
                self._thumb_images.append(tk_img)
                self._grid_canvas.create_image(ix, iy, anchor="nw", image=tk_img, tags=(tag,))
            except Exception:
                self._thumb_images.append(None)
                self._grid_canvas.create_text(
                    x + thumb // 2, y + thumb // 2,
                    text="読込失敗", fill=T_SECONDARY, font=("", 9), tags=(tag,)
                )

            name = photo_path.name
            if len(name) > 18:
                name = name[:15] + "..."
            self._grid_canvas.create_text(
                x + thumb // 2, y + thumb + 9,
                text=name,
                fill=T_PRIMARY if is_current else T_SECONDARY,
                font=("", 8), tags=(tag,), width=thumb
            )

            rating_info = self._ratings.get(str(photo_path), {})
            stars = rating_info.get("stars", 0)
            flagged = rating_info.get("flag", False)
            badge_parts = []
            if flagged:
                badge_parts.append("🚩")
            if stars:
                badge_parts.append("★" * stars)
            if badge_parts:
                self._grid_canvas.create_text(
                    x + thumb // 2, y + thumb + 26,
                    text=" ".join(badge_parts), fill=AMBER, font=("", 8), tags=(tag,)
                )

            self._grid_canvas.tag_bind(tag, "<Button-1>", lambda e, idx=i: self._grid_click(idx))

        rows = (len(self.photos) + cols - 1) // cols
        total_h = rows * (cell_h + pad) + pad
        self._grid_canvas.configure(scrollregion=(0, 0, gw, total_h))

        if self.photos:
            current_row = self.current_index // cols
            frac = current_row * (cell_h + pad) / max(total_h, 1)
            self._grid_canvas.yview_moveto(max(0.0, frac - 0.1))

    def _grid_click(self, index: int):
        self.current_index = index
        self._exit_grid_mode()

    # ── 評価・フラグ ──────────────────────────────────────────

    def _set_rating(self, stars: int):
        if not self.photos or self.current_index >= len(self.photos):
            return
        key = str(self.photos[self.current_index])
        current = self._ratings.get(key, {})
        current["stars"] = 0 if current.get("stars") == stars else stars
        self._ratings[key] = current
        self.config_data["ratings"] = self._ratings
        save_config(self.config_data)
        self._update_rating_bar()

    def _toggle_flag(self):
        if not self.photos or self.current_index >= len(self.photos):
            return
        key = str(self.photos[self.current_index])
        current = self._ratings.get(key, {})
        current["flag"] = not current.get("flag", False)
        self._ratings[key] = current
        self.config_data["ratings"] = self._ratings
        save_config(self.config_data)
        self._update_rating_bar()
        msg = "🚩 フラグを設定しました" if current["flag"] else "🏳 フラグを解除しました"
        self._show_toast(msg)

    def _update_rating_bar(self):
        if not self._star_labels:
            return
        stars, flagged = 0, False
        if self.photos and self.current_index < len(self.photos):
            info = self._ratings.get(str(self.photos[self.current_index]), {})
            stars = info.get("stars", 0)
            flagged = info.get("flag", False)
        for i, lbl in enumerate(self._star_labels):
            lbl.config(text="★" if i < stars else "☆", fg=AMBER if i < stars else T_MUTED)
        if self._flag_label:
            self._flag_label.config(
                text="🚩" if flagged else "🏳",
                fg="#ef4444" if flagged else T_MUTED
            )

    # ── モザイク機能 ──────────────────────────

    def _toggle_mosaic_mode(self):
        if not PIL_AVAILABLE:
            messagebox.showerror(
                "Pillowが必要です",
                "この機能にはPillowが必要です。\n\n  pip install Pillow\n\nインストール後に再起動してください。"
            )
            return
        self._mosaic_mode = not self._mosaic_mode
        if self._mosaic_mode:
            self._enter_mosaic_mode()
        else:
            self._exit_mosaic_mode()

    def _enter_mosaic_mode(self):
        # トリミングモードが有効なら解除
        if self._crop_mode:
            self._exit_crop_mode()
        self._mosaic_btn.config(bg="#7c3aed", text="🔲  モザイク解除")
        self._mosaic_btn.bind("<Enter>", lambda e: self._mosaic_btn.config(bg="#9333ea"))
        self._mosaic_btn.bind("<Leave>", lambda e: self._mosaic_btn.config(bg="#7c3aed"))
        self._mosaic_bar.pack(fill="x", after=self._prog_canvas)
        self.canvas.config(cursor="crosshair")
        self.canvas.bind("<ButtonPress-1>",   self._mosaic_press)
        self.canvas.bind("<B1-Motion>",        self._mosaic_move)
        self.canvas.bind("<ButtonRelease-1>",  self._mosaic_release)

    def _exit_mosaic_mode(self):
        self._mosaic_mode = False
        self._mosaic_btn.config(bg=BG_WIDGET, text="🔲  モザイク")
        self._mosaic_btn.bind("<Enter>", lambda e: self._mosaic_btn.config(bg=BG_HOVER))
        self._mosaic_btn.bind("<Leave>", lambda e: self._mosaic_btn.config(bg=BG_WIDGET))
        self._mosaic_bar.pack_forget()
        self.canvas.config(cursor="")
        self.canvas.unbind("<ButtonPress-1>")
        self.canvas.unbind("<B1-Motion>")
        self.canvas.unbind("<ButtonRelease-1>")
        if self._mosaic_rect:
            self.canvas.delete(self._mosaic_rect)
            self._mosaic_rect = None
        self._mosaic_start = None

    def _mosaic_press(self, event):
        self._mosaic_start = (event.x, event.y)
        if self._mosaic_rect:
            self.canvas.delete(self._mosaic_rect)
            self._mosaic_rect = None

    def _mosaic_move(self, event):
        if not self._mosaic_start:
            return
        if self._mosaic_rect:
            self.canvas.delete(self._mosaic_rect)
        x0, y0 = self._mosaic_start
        self._mosaic_rect = self.canvas.create_rectangle(
            x0, y0, event.x, event.y,
            outline="#ff4444", width=2, dash=(6, 3)
        )

    def _mosaic_release(self, event):
        if not self._mosaic_start:
            return
        x0, y0 = self._mosaic_start
        x1, y1 = event.x, event.y
        self._mosaic_start = None

        rx0, rx1 = min(x0, x1), max(x0, x1)
        ry0, ry1 = min(y0, y1), max(y0, y1)

        if rx1 - rx0 < 5 or ry1 - ry0 < 5:
            if self._mosaic_rect:
                self.canvas.delete(self._mosaic_rect)
                self._mosaic_rect = None
            return

        self._apply_mosaic_to_selection(rx0, ry0, rx1, ry1)

    def _apply_mosaic_to_selection(self, cx0: int, cy0: int, cx1: int, cy1: int):
        if not self._display_info or not self.photos:
            return

        scale, offset_x, offset_y, orig_w, orig_h = self._display_info

        # canvas座標 → 元画像座標に変換
        ix0 = int((cx0 - offset_x) * scale)
        iy0 = int((cy0 - offset_y) * scale)
        ix1 = int((cx1 - offset_x) * scale)
        iy1 = int((cy1 - offset_y) * scale)

        # 元画像の範囲内にクランプ
        ix0 = max(0, min(ix0, orig_w))
        iy0 = max(0, min(iy0, orig_h))
        ix1 = max(0, min(ix1, orig_w))
        iy1 = max(0, min(iy1, orig_h))

        if ix1 <= ix0 or iy1 <= iy0:
            return

        block_size = self._mosaic_strength.get()
        photo_path = self.photos[self.current_index]

        try:
            img = Image.open(photo_path)
            img = ImageOps.exif_transpose(img)

            region = img.crop((ix0, iy0, ix1, iy1))
            rw, rh = region.size

            # ピクセル化：縮小してから拡大
            small_w = max(1, rw // block_size)
            small_h = max(1, rh // block_size)
            small = region.resize((small_w, small_h), Image.BOX)
            pixelated = small.resize((rw, rh), Image.NEAREST)

            img.paste(pixelated, (ix0, iy0))

            suffix = photo_path.suffix.lower()
            if suffix in {".jpg", ".jpeg"}:
                img.save(photo_path, "JPEG", quality=95, subsampling=0)
            elif suffix == ".png":
                img.save(photo_path, "PNG")
            elif suffix == ".webp":
                img.save(photo_path, "WEBP", quality=95)
            else:
                img.save(photo_path)

            if self._mosaic_rect:
                self.canvas.delete(self._mosaic_rect)
                self._mosaic_rect = None

            self._show_current()
            self._show_toast("モザイク適用完了")

        except Exception as e:
            messagebox.showerror("エラー", f"モザイクの適用に失敗しました:\n{e}")

    # ── トリミング機能 ────────────────────────

    def _toggle_crop_mode(self):
        if not PIL_AVAILABLE:
            messagebox.showerror(
                "Pillowが必要です",
                "この機能にはPillowが必要です。\n\n  pip install Pillow\n\nインストール後に再起動してください。"
            )
            return
        self._crop_mode = not self._crop_mode
        if self._crop_mode:
            self._enter_crop_mode()
        else:
            self._exit_crop_mode()

    def _enter_crop_mode(self):
        # モザイクモードが有効なら解除
        if self._mosaic_mode:
            self._exit_mosaic_mode()
        self._crop_btn.config(bg="#065f46", text="✂  トリミング解除")
        self._crop_btn.bind("<Enter>", lambda e: self._crop_btn.config(bg="#047857"))
        self._crop_btn.bind("<Leave>", lambda e: self._crop_btn.config(bg="#065f46"))
        self._crop_bar.pack(fill="x", after=self._prog_canvas)
        self.canvas.config(cursor="crosshair")
        self.canvas.bind("<ButtonPress-1>",  self._crop_press)
        self.canvas.bind("<B1-Motion>",       self._crop_move)
        self.canvas.bind("<ButtonRelease-1>", self._crop_release)

    def _exit_crop_mode(self):
        self._crop_mode = False
        self._crop_btn.config(bg=BG_WIDGET, text="✂  トリミング")
        self._crop_btn.bind("<Enter>", lambda e: self._crop_btn.config(bg=BG_HOVER))
        self._crop_btn.bind("<Leave>", lambda e: self._crop_btn.config(bg=BG_WIDGET))
        self._crop_bar.pack_forget()
        self.canvas.config(cursor="")
        self.canvas.unbind("<ButtonPress-1>")
        self.canvas.unbind("<B1-Motion>")
        self.canvas.unbind("<ButtonRelease-1>")
        if self._crop_rect:
            self.canvas.delete(self._crop_rect)
            self._crop_rect = None
        self._crop_start = None

    def _crop_press(self, event):
        self._crop_start = (event.x, event.y)
        if self._crop_rect:
            self.canvas.delete(self._crop_rect)
            self._crop_rect = None

    def _crop_move(self, event):
        if not self._crop_start:
            return
        if self._crop_rect:
            self.canvas.delete(self._crop_rect)
        x0, y0 = self._crop_start
        self._crop_rect = self.canvas.create_rectangle(
            x0, y0, event.x, event.y,
            outline="#22c55e", width=2, dash=(6, 3)
        )

    def _crop_release(self, event):
        if not self._crop_start:
            return
        x0, y0 = self._crop_start
        x1, y1 = event.x, event.y
        self._crop_start = None

        rx0, rx1 = min(x0, x1), max(x0, x1)
        ry0, ry1 = min(y0, y1), max(y0, y1)

        if rx1 - rx0 < 5 or ry1 - ry0 < 5:
            if self._crop_rect:
                self.canvas.delete(self._crop_rect)
                self._crop_rect = None
            return

        self._confirm_and_apply_crop(rx0, ry0, rx1, ry1)

    def _confirm_and_apply_crop(self, cx0: int, cy0: int, cx1: int, cy1: int):
        if not self._display_info or not self.photos:
            return

        scale, offset_x, offset_y, orig_w, orig_h = self._display_info

        ix0 = int((cx0 - offset_x) * scale)
        iy0 = int((cy0 - offset_y) * scale)
        ix1 = int((cx1 - offset_x) * scale)
        iy1 = int((cy1 - offset_y) * scale)

        ix0 = max(0, min(ix0, orig_w))
        iy0 = max(0, min(iy0, orig_h))
        ix1 = max(0, min(ix1, orig_w))
        iy1 = max(0, min(iy1, orig_h))

        if ix1 <= ix0 or iy1 <= iy0:
            return

        crop_w = ix1 - ix0
        crop_h = iy1 - iy0
        photo_path = self.photos[self.current_index]

        confirmed = messagebox.askyesno(
            "トリミングの確認",
            f"選択範囲にトリミングしますか？\n\n"
            f"  サイズ: {crop_w} × {crop_h} px\n"
            f"  ファイル: {photo_path.name}\n\n"
            "この操作は元に戻せません。",
            icon="warning"
        )

        if self._crop_rect:
            self.canvas.delete(self._crop_rect)
            self._crop_rect = None

        if not confirmed:
            return

        try:
            img = Image.open(photo_path)
            img = ImageOps.exif_transpose(img)
            cropped = img.crop((ix0, iy0, ix1, iy1))

            suffix = photo_path.suffix.lower()
            if suffix in {".jpg", ".jpeg"}:
                cropped.save(photo_path, "JPEG", quality=95, subsampling=0)
            elif suffix == ".png":
                cropped.save(photo_path, "PNG")
            elif suffix == ".webp":
                cropped.save(photo_path, "WEBP", quality=95)
            else:
                cropped.save(photo_path)

            self._show_current()
            self._show_toast(f"✂  トリミング完了  {crop_w}×{crop_h}px")

        except Exception as e:
            messagebox.showerror("エラー", f"トリミングに失敗しました:\n{e}")

    def _show_done(self):
        self.filename_label.config(text="")
        self.counter_label.config(text="完了")
        self.title("Photo Sorter — 完了")

        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        self.canvas.create_text(
            cw // 2, ch // 2,
            text=f"✓  {self.sorted_count} 枚の仕分けが完了しました",
            fill=SUCCESS, font=("", 18, "bold"), justify="center"
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
