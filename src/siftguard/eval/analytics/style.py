"""Matplotlib style — GCP-themed, accessible, print-quality.

All panels import this module to ensure visual consistency.
"""
from __future__ import annotations

import matplotlib.pyplot as plt
import matplotlib as mpl

# GCP palette matching dashboard
BLUE    = "#1a73e8"
YELLOW  = "#fbbc04"
GREEN   = "#34a853"
RED     = "#ea4335"
GRAY    = "#5f6368"
LGRAY   = "#dadce0"
BG      = "#ffffff"
PANEL_BG = "#f8f9fa"

PALETTE = [BLUE, GREEN, YELLOW, RED, GRAY, "#9334e6", "#24c1e0"]

def apply_style() -> None:
    mpl.rcParams.update({
        "figure.facecolor":     BG,
        "axes.facecolor":       PANEL_BG,
        "axes.edgecolor":       LGRAY,
        "axes.labelcolor":      GRAY,
        "axes.titlesize":       13,
        "axes.labelsize":       10,
        "axes.grid":            True,
        "axes.prop_cycle":      mpl.cycler(color=PALETTE),
        "grid.color":           LGRAY,
        "grid.linewidth":       0.8,
        "grid.zorder":          0,
        "xtick.color":          GRAY,
        "ytick.color":          GRAY,
        "xtick.labelsize":      9,
        "ytick.labelsize":      9,
        "legend.fontsize":      9,
        "legend.framealpha":    0.9,
        "legend.edgecolor":     LGRAY,
        "font.family":          "sans-serif",
        "font.size":            10,
        "figure.dpi":           200,
        "savefig.dpi":          200,
        "savefig.bbox":         "tight",
        "savefig.facecolor":    BG,
        "lines.linewidth":      2.0,
        "lines.markersize":     7,
    })


def add_claim(ax: mpl.axes.Axes, claim: str) -> None:
    """Add claim as figure subtitle below the panel title."""
    ax.set_xlabel(
        ax.get_xlabel(),
    )
    ax.annotate(
        f"Claim: {claim}",
        xy=(0.5, -0.18),
        xycoords="axes fraction",
        ha="center", va="top",
        fontsize=8, color=GRAY,
        style="italic",
        wrap=True,
    )


def placeholder(ax: mpl.axes.Axes, title: str, reason: str) -> None:
    """Render an explanatory placeholder when panel cannot be produced."""
    ax.set_facecolor(PANEL_BG)
    ax.set_title(title, fontsize=13, color=GRAY)
    ax.text(
        0.5, 0.5,
        f"Panel unavailable\n\n{reason}",
        transform=ax.transAxes,
        ha="center", va="center",
        fontsize=10, color=GRAY,
        style="italic",
        bbox=dict(boxstyle="round,pad=0.5", facecolor=BG,
                  edgecolor=LGRAY, linewidth=1),
    )
    ax.set_xticks([])
    ax.set_yticks([])