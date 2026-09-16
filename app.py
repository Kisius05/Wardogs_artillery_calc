#!/usr/bin/env python3
"""War Dogs artillery range calculator."""

from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

import customtkinter as ctk

NUMBER_RE = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)")
COPY_ICON = "⎘"

FULL_MIN_WIDTH = 460
COMPACT_MIN_WIDTH = 340

COLORS = {
    "bg": "#1b2838",
    "panel": "#243447",
    "border": "#3d5570",
    "accent": "#4ea3e0",
    "text": "#e8eef4",
    "muted": "#9bb0c4",
    "input": "#16202c",
    "result": "#6ec8ff",
    "warn": "#f0c36e",
}

CARDINALS = {
    "en": ["N", "NE", "E", "SE", "S", "SW", "W", "NW"],
    "ru": ["С", "СВ", "В", "ЮВ", "Ю", "ЮЗ", "З", "СЗ"],
}

STRINGS = {
    "en": {
        "window_title": "War Dogs — Artillery",
        "heading": "Artillery range",
        "gun": "Gun position",
        "gun_hint": "98.43, 110.38",
        "target": "Target",
        "target_hint": "94.53, 109.03",
        "copy": "Copy range and °",
        "copied": "Copied",
        "always_on_top": "Always on top",
        "empty": "Paste both coordinates to get range and azimuth.",
        "invalid": "Need two numbers: X, Y",
        "same_point": "Gun and target are the same point.",
        "meters": "m",
        "exact": "exact",
        "mils": "az mils",
        "breakdown_title": "The maths",
        "step_a": "a = difference in X",
        "step_b": "b = difference in Y",
        "step_c": "c = √(a² + b²)",
        "step_range": "range in metres = c × 100",
        "step_az": "azimuth = atan2(ΔX, ΔY), 0–360°, 0° = north",
        "compact": "Compact",
        "full": "Full",
        "mode_full": "full",
        "mode_compact": "comp.",
    },
    "ru": {
        "window_title": "War Dogs — Артиллерия",
        "heading": "Дальность артиллерии",
        "gun": "Позиция пушки",
        "gun_hint": "98.43, 110.38",
        "target": "Цель",
        "target_hint": "94.53, 109.03",
        "copy": "Копировать дальность и °",
        "copied": "Скопировано",
        "always_on_top": "Поверх всех окон",
        "empty": "Вставьте обе координаты, чтобы получить дальность и азимут.",
        "invalid": "Нужны два числа: X, Y",
        "same_point": "Пушка и цель в одной точке.",
        "meters": "м",
        "exact": "точно",
        "mils": "аз. милы",
        "breakdown_title": "Расчёт",
        "step_a": "a = разница по X",
        "step_b": "b = разница по Y",
        "step_c": "c = √(a² + b²)",
        "step_range": "дальность в метрах = c × 100",
        "step_az": "азимут = atan2(ΔX, ΔY), 0–360°, 0° = север",
        "compact": "Компакт",
        "full": "Полный",
        "mode_full": "пол.",
        "mode_compact": "комп.",
    },
}


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def settings_path() -> Path:
    return app_dir() / "settings.json"


def load_settings() -> dict:
    defaults = {"language": "ru", "compact": False}
    path = settings_path()
    if not path.is_file():
        return defaults
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return defaults
    language = data.get("language", "ru")
    if language not in STRINGS:
        language = "ru"
    return {"language": language, "compact": bool(data.get("compact", False))}


def save_settings(settings: dict) -> None:
    try:
        settings_path().write_text(
            json.dumps(settings, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError:
        pass


def parse_coords(text: str) -> tuple[float, float] | None:
    nums = NUMBER_RE.findall(text.strip())
    if len(nums) < 2:
        return None
    try:
        return float(nums[0]), float(nums[1])
    except ValueError:
        return None


def cardinal_name(degrees: float, lang: str) -> str:
    names = CARDINALS.get(lang, CARDINALS["en"])
    return names[round(degrees / 45) % 8]


def calculate_range(
    gun: tuple[float, float], target: tuple[float, float]
) -> dict[str, float | None]:
    gx, gy = gun
    tx, ty = target
    dx = tx - gx
    dy = ty - gy
    sum_sq = dx * dx + dy * dy
    c = math.hypot(dx, dy)
    range_m = c * 100
    if c == 0:
        azimuth = None
        az_mils = None
    else:
        azimuth = (math.degrees(math.atan2(dx, dy)) + 360.0) % 360.0
        shown = round(azimuth, 1)
        if shown >= 360.0:
            shown = 0.0
        az_mils = shown * 6400.0 / 360.0
    return {
        "dx": dx,
        "dy": dy,
        "a": abs(dx),
        "b": abs(dy),
        "sum_sq": sum_sq,
        "c": c,
        "range": range_m,
        "rounded": float(round(range_m)),
        "azimuth": azimuth,
        "az_mils": az_mils,
    }


class App(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.settings = load_settings()
        self.lang = self.settings["language"]
        self.compact = bool(self.settings.get("compact", False))
        self._copy_reset_id: str | None = None
        self._fit_after_id: str | None = None

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self.title(self.t("window_title"))
        self.configure(fg_color=COLORS["bg"])

        self.gun_var = ctk.StringVar()
        self.target_var = ctk.StringVar()
        self.lang_var = ctk.StringVar(value=self.lang.upper())
        self.mode_var = ctk.StringVar(
            value=STRINGS[self.lang]["mode_compact"] if self.compact else STRINGS[self.lang]["mode_full"]
        )
        self._syncing_mode = False
        self.topmost_var = ctk.BooleanVar(value=False)

        self.gun_var.trace_add("write", self._on_input)
        self.target_var.trace_add("write", self._on_input)

        self._build()
        self._apply_language()
        self._apply_layout()
        self._recalculate()
        self._schedule_fit()

    def t(self, key: str) -> str:
        return STRINGS[self.lang][key]

    def _build(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)

        self.outer = ctk.CTkFrame(self, fg_color=COLORS["bg"])
        self.outer.grid(row=0, column=0, sticky="new", padx=18, pady=16)
        self.outer.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(self.outer, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=1)

        self.heading = ctk.CTkLabel(
            header,
            text="",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=COLORS["accent"],
            anchor="w",
        )
        self.heading.grid(row=0, column=0, sticky="w")

        controls = ctk.CTkFrame(header, fg_color="transparent")
        controls.grid(row=0, column=1, sticky="e")

        self.mode_switch = ctk.CTkSegmentedButton(
            controls,
            values=[STRINGS[self.lang]["mode_full"], STRINGS[self.lang]["mode_compact"]],
            variable=self.mode_var,
            command=self._on_mode,
            width=128,
            height=28,
            font=ctk.CTkFont(size=12, weight="bold"),
            selected_color=COLORS["accent"],
            selected_hover_color="#3d8ec4",
            unselected_color=COLORS["panel"],
            unselected_hover_color=COLORS["border"],
            fg_color=COLORS["panel"],
            text_color=COLORS["text"],
        )
        self.mode_switch.grid(row=0, column=0, padx=(0, 8))

        self.lang_switch = ctk.CTkSegmentedButton(
            controls,
            values=["RU", "EN"],
            variable=self.lang_var,
            command=self._on_language,
            width=110,
            height=28,
            font=ctk.CTkFont(size=12, weight="bold"),
            selected_color=COLORS["accent"],
            selected_hover_color="#3d8ec4",
            unselected_color=COLORS["panel"],
            unselected_hover_color=COLORS["border"],
            fg_color=COLORS["panel"],
            text_color=COLORS["text"],
        )
        self.lang_switch.grid(row=0, column=1)

        self.gun_label = ctk.CTkLabel(
            self.outer,
            text="",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLORS["text"],
            anchor="w",
        )
        self.gun_label.grid(row=1, column=0, sticky="ew", pady=(16, 0))

        self.gun_entry = ctk.CTkEntry(
            self.outer,
            textvariable=self.gun_var,
            height=40,
            font=ctk.CTkFont(size=15),
            fg_color=COLORS["input"],
            border_color=COLORS["border"],
            text_color=COLORS["text"],
            placeholder_text_color=COLORS["muted"],
        )
        self.gun_entry.grid(row=3, column=0, sticky="ew", pady=(4, 12))

        self.target_label = ctk.CTkLabel(
            self.outer,
            text="",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLORS["text"],
            anchor="w",
        )
        self.target_label.grid(row=4, column=0, sticky="ew")

        self.target_entry = ctk.CTkEntry(
            self.outer,
            textvariable=self.target_var,
            height=40,
            font=ctk.CTkFont(size=15),
            fg_color=COLORS["input"],
            border_color=COLORS["border"],
            text_color=COLORS["text"],
            placeholder_text_color=COLORS["muted"],
        )
        self.target_entry.grid(row=5, column=0, sticky="ew", pady=(4, 16))

        self.result_card = ctk.CTkFrame(
            self.outer,
            fg_color=COLORS["panel"],
            border_color=COLORS["border"],
            border_width=1,
            corner_radius=10,
        )
        self.result_card.grid(row=6, column=0, sticky="ew")
        self.result_card.grid_columnconfigure(0, weight=1)
        self.result_card.grid_columnconfigure(1, weight=1)

        self.result_main = ctk.CTkLabel(
            self.result_card,
            text="",
            font=ctk.CTkFont(size=32, weight="bold"),
            text_color=COLORS["result"],
        )
        self.result_main.grid(row=0, column=0, pady=(16, 0), padx=(12, 6), sticky="ew")

        self.result_az = ctk.CTkLabel(
            self.result_card,
            text="",
            font=ctk.CTkFont(size=32, weight="bold"),
            text_color=COLORS["result"],
        )
        self.result_az.grid(row=0, column=1, pady=(16, 0), padx=(6, 12), sticky="ew")

        self.result_exact = ctk.CTkLabel(
            self.result_card,
            text="",
            font=ctk.CTkFont(size=11),
            text_color=COLORS["muted"],
            wraplength=400,
            justify="center",
        )
        self.result_exact.grid(row=1, column=0, columnspan=2, pady=(2, 16), padx=12, sticky="ew")

        self.result_az_sub = ctk.CTkLabel(
            self.result_card,
            text="",
            font=ctk.CTkFont(size=13),
            text_color=COLORS["muted"],
        )
        self.result_az_sub.grid(row=1, column=1, pady=(2, 16), padx=(6, 12), sticky="ew")

        self.math_card = ctk.CTkFrame(
            self.outer,
            fg_color=COLORS["panel"],
            border_color=COLORS["border"],
            border_width=1,
            corner_radius=10,
        )
        self.math_card.grid(row=7, column=0, sticky="ew", pady=(12, 0))
        self.math_card.grid_columnconfigure(0, weight=1)

        self.math_title = ctk.CTkLabel(
            self.math_card,
            text="",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLORS["accent"],
            anchor="w",
        )
        self.math_title.grid(row=0, column=0, sticky="ew", padx=14, pady=(10, 2))

        self.math_body = ctk.CTkLabel(
            self.math_card,
            text="",
            font=ctk.CTkFont(family="Consolas", size=13),
            text_color=COLORS["text"],
            justify="left",
            anchor="w",
        )
        self.math_body.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 10))

        self.footer = ctk.CTkFrame(self.outer, fg_color="transparent")
        self.footer.grid(row=8, column=0, sticky="ew", pady=(12, 0))
        self.footer.grid_columnconfigure(1, weight=1)

        self.copy_btn = ctk.CTkButton(
            self.footer,
            text="",
            height=36,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=COLORS["accent"],
            hover_color="#3d8ec4",
            text_color="#102030",
            command=self._copy_result,
            state="disabled",
        )
        self.copy_btn.grid(row=0, column=0, sticky="w")

        self.topmost_check = ctk.CTkCheckBox(
            self.footer,
            text="",
            variable=self.topmost_var,
            command=self._on_topmost,
            font=ctk.CTkFont(size=13),
            text_color=COLORS["text"],
            fg_color=COLORS["accent"],
            hover_color="#3d8ec4",
            border_color=COLORS["border"],
            checkmark_color="#102030",
        )
        self.topmost_check.grid(row=0, column=2, sticky="e")

        self._last_rounded: int | None = None
        self._last_azimuth: float | None = None

    def _apply_language(self) -> None:
        self.title(self.t("window_title"))
        self.heading.configure(text=self.t("heading"))
        self.gun_label.configure(text=self.t("gun"))
        self.target_label.configure(text=self.t("target"))
        self.gun_entry.configure(placeholder_text=self.t("gun_hint"))
        self.target_entry.configure(placeholder_text=self.t("target_hint"))
        self.math_title.configure(text=self.t("breakdown_title"))
        self.topmost_check.configure(text=self.t("always_on_top"))
        self._apply_copy_label()
        self._apply_compact_button()
        self._recalculate()
        self._schedule_fit()

    def _apply_compact_button(self) -> None:
        full_label = self.t("mode_full")
        compact_label = self.t("mode_compact")
        self._syncing_mode = True
        try:
            self.mode_switch.configure(values=[full_label, compact_label])
            self.mode_var.set(compact_label if self.compact else full_label)
        finally:
            self._syncing_mode = False

    def _on_mode(self, value: str) -> None:
        if self._syncing_mode:
            return
        want_compact = value == self.t("mode_compact")
        if want_compact == self.compact:
            return
        self.compact = want_compact
        self.settings["compact"] = self.compact
        save_settings(self.settings)
        self._apply_layout()
        self._recalculate()
        self._schedule_fit()

    def _apply_copy_label(self, copied: bool = False) -> None:
        if copied:
            label = "✓" if self.compact else self.t("copied")
        elif self.compact:
            label = COPY_ICON
        else:
            label = self.t("copy")
        width = 36 if self.compact else 220
        font = ctk.CTkFont(size=16) if self.compact else ctk.CTkFont(size=13, weight="bold")
        self.copy_btn.configure(text=label, width=width, font=font)

    def _apply_layout(self) -> None:
        if self.compact:
            self.outer.grid_configure(padx=12, pady=(10, 12))
            self.heading.grid_remove()
            self.math_card.grid_remove()
            self.gun_label.grid_configure(pady=(8, 0))
            self.gun_entry.configure(height=32, font=ctk.CTkFont(size=14))
            self.target_entry.configure(height=32, font=ctk.CTkFont(size=14))
            self.target_entry.grid_configure(pady=(4, 10))
            self.result_main.configure(font=ctk.CTkFont(size=24, weight="bold"))
            self.result_az.configure(font=ctk.CTkFont(size=24, weight="bold"))
            self.result_main.grid_configure(pady=(10, 0))
            self.result_az.grid_configure(pady=(10, 0))
            self.footer.grid_configure(pady=(10, 0))
            self.topmost_check.configure(font=ctk.CTkFont(size=12))
        else:
            self.outer.grid_configure(padx=18, pady=16)
            self.heading.grid()
            self.math_card.grid()
            self.gun_label.grid_configure(pady=(16, 0))
            self.gun_entry.configure(height=40, font=ctk.CTkFont(size=15))
            self.target_entry.configure(height=40, font=ctk.CTkFont(size=15))
            self.target_entry.grid_configure(pady=(4, 16))
            self.result_main.configure(font=ctk.CTkFont(size=32, weight="bold"))
            self.result_az.configure(font=ctk.CTkFont(size=32, weight="bold"))
            self.result_main.grid_configure(pady=(16, 0))
            self.result_az.grid_configure(pady=(16, 0))
            self.footer.grid_configure(pady=(12, 0))
            self.topmost_check.configure(font=ctk.CTkFont(size=13))

        self._apply_compact_button()
        self._apply_copy_label()
        self._schedule_fit()

    def _schedule_fit(self) -> None:
        if self._fit_after_id is not None:
            try:
                self.after_cancel(self._fit_after_id)
            except Exception:
                pass
        self._fit_after_id = self.after_idle(self._fit_to_content)

    def _fit_to_content(self) -> None:
        self._fit_after_id = None
        self.minsize(0, 0)
        self.update_idletasks()

        info = self.outer.grid_info()
        padx = info.get("padx", 0)
        pady = info.get("pady", 0)
        if isinstance(padx, (tuple, list)):
            pad_x = int(padx[0]) + int(padx[-1])
        else:
            pad_x = int(padx) * 2
        if isinstance(pady, (tuple, list)):
            pad_y = int(pady[0]) + int(pady[-1])
        else:
            pad_y = int(pady) * 2

        pixel_w = self.outer.winfo_reqwidth() + pad_x
        pixel_h = self.outer.winfo_reqheight() + pad_y
        width = max(self._reverse_window_scaling(pixel_w), COMPACT_MIN_WIDTH if self.compact else FULL_MIN_WIDTH)
        height = self._reverse_window_scaling(pixel_h) + 4
        self.minsize(width, height)
        self.geometry(f"{width}x{height}")

    def _on_language(self, value: str) -> None:
        lang = value.lower()
        if lang not in STRINGS or lang == self.lang:
            return
        self.lang = lang
        self.settings["language"] = lang
        save_settings(self.settings)
        self._apply_language()

    def _on_topmost(self) -> None:
        self.attributes("-topmost", bool(self.topmost_var.get()))

    def _on_input(self, *_args) -> None:
        self._recalculate()

    def _coord_state(self, text: str) -> str:
        if not text.strip():
            return "empty"
        return "ok" if parse_coords(text) else "invalid"

    def _formula_text(self) -> str:
        return (
            f"{self.t('step_a')}\n"
            f"{self.t('step_b')}\n"
            f"{self.t('step_c')}\n"
            f"{self.t('step_range')}\n"
            f"{self.t('step_az')}"
        )

    def _recalculate(self) -> None:
        gun_text = self.gun_var.get()
        target_text = self.target_var.get()
        gun_state = self._coord_state(gun_text)
        target_state = self._coord_state(target_text)
        formula = self._formula_text()

        if gun_state == "empty" and target_state == "empty":
            self._show_idle(self.t("empty"), formula)
            return
        if gun_state == "invalid" or target_state == "invalid":
            self._show_idle(self.t("invalid"), formula, warning=True)
            return
        if gun_state == "empty" or target_state == "empty":
            self._show_idle(self.t("empty"), formula)
            return

        gun = parse_coords(gun_text)
        target = parse_coords(target_text)
        if gun is None or target is None:
            self._show_idle(self.t("invalid"), formula, warning=True)
            return

        result = calculate_range(gun, target)
        rounded = int(result["rounded"])
        unit = self.t("meters")
        azimuth = result["azimuth"]
        az_mils = result["az_mils"]
        self._last_rounded = rounded
        self._last_azimuth = azimuth

        result_font = 24 if self.compact else 32
        sub_font = 11 if self.compact else 13
        self.result_main.configure(
            text=f"{rounded} {unit}",
            text_color=COLORS["result"],
            font=ctk.CTkFont(size=result_font, weight="bold"),
        )
        wrap = 280 if self.compact else 0
        self.result_exact.configure(
            text=f"{result['range']:.1f} {unit} · {self.t('exact')}",
            text_color=COLORS["muted"],
            font=ctk.CTkFont(size=sub_font),
            wraplength=wrap,
        )
        self.result_exact.grid(row=1, column=0, columnspan=1, pady=(2, 10 if self.compact else 16), padx=(12, 6), sticky="ew")
        self.result_az_sub.grid(row=1, column=1, pady=(2, 10 if self.compact else 16), padx=(6, 12), sticky="ew")

        if azimuth is None:
            self.result_az.configure(
                text="—",
                text_color=COLORS["muted"],
                font=ctk.CTkFont(size=result_font, weight="bold"),
            )
            self.result_az_sub.configure(
                text=self.t("same_point"),
                text_color=COLORS["warn"],
                font=ctk.CTkFont(size=sub_font),
            )
        else:
            self.result_az.configure(
                text=f"{azimuth:.1f}°",
                text_color=COLORS["result"],
                font=ctk.CTkFont(size=result_font, weight="bold"),
            )
            self.result_az_sub.configure(
                text=f"{cardinal_name(azimuth, self.lang)} · {az_mils:.0f} {self.t('mils')}",
                text_color=COLORS["muted"],
                font=ctk.CTkFont(size=sub_font),
            )

        az_line = (
            self.t("same_point")
            if azimuth is None
            else (
                f"ΔX = {result['dx']:+.2f}   ΔY = {result['dy']:+.2f}\n"
                f"atan2(ΔX, ΔY) = {azimuth:.1f}°  ({cardinal_name(azimuth, self.lang)})\n"
                f"{self.t('mils')} = {az_mils:.0f}"
            )
        )
        self.math_body.configure(
            text=(
                f"a = {result['a']:.2f}\n"
                f"b = {result['b']:.2f}\n"
                f"a² + b² = {result['a'] ** 2:.2f} + {result['b'] ** 2:.2f}"
                f" = {result['sum_sq']:.2f}\n"
                f"√{result['sum_sq']:.2f} = {result['c']:.3f}\n"
                f"{result['c']:.3f} × 100 = {rounded} {unit}\n"
                f"{az_line}"
            )
        )
        self.copy_btn.configure(state="normal")
        self._apply_copy_label()

    def _show_idle(self, message: str, formula: str, warning: bool = False) -> None:
        self._last_rounded = None
        self._last_azimuth = None
        color = COLORS["warn"] if warning else COLORS["muted"]
        result_font = 24 if self.compact else 32
        self.result_main.configure(
            text="—",
            text_color=COLORS["muted"],
            font=ctk.CTkFont(size=result_font, weight="bold"),
        )
        self.result_az.configure(
            text="—",
            text_color=COLORS["muted"],
            font=ctk.CTkFont(size=result_font, weight="bold"),
        )
        self.result_exact.configure(
            text=message,
            text_color=color,
            font=ctk.CTkFont(size=11),
            wraplength=280 if self.compact else 400,
        )
        self.result_exact.grid(
            row=1,
            column=0,
            columnspan=2,
            pady=(2, 10 if self.compact else 16),
            padx=12,
            sticky="ew",
        )
        self.result_az_sub.grid_remove()
        self.math_body.configure(text=formula)
        self.copy_btn.configure(state="disabled")
        self._apply_copy_label()

    def _flash_copy(self) -> None:
        self._apply_copy_label(copied=True)
        if self._copy_reset_id is not None:
            self.after_cancel(self._copy_reset_id)
        self._copy_reset_id = self.after(1400, self._apply_copy_label)

    def _copy_result(self) -> None:
        if self._last_rounded is None:
            return
        if self._last_azimuth is None:
            text = str(self._last_rounded)
        else:
            text = f"{self._last_rounded}  {self._last_azimuth:.1f}°"
        self.clipboard_clear()
        self.clipboard_append(text)
        self._flash_copy()


def main() -> None:
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
