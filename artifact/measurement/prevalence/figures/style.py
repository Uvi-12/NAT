"""Shared publication style for the NAT paper figures (IEEE compsoc, Times body)."""
import matplotlib as mpl
import matplotlib.pyplot as plt

# verdict palette (CVD-validated; severity-ordered). N/A neutral gray.
V = dict(Exposed="#C1483B", Conditional="#E6A23C", Transitive="#7A5195",
         Resistant="#2A9D8F", NA="#9AA0A6")
INK   = "#1A1A1A"   # primary text
INK2  = "#5A5A5A"   # secondary text
GRID  = "#E7E7E4"
SURF  = "#FFFFFF"
HATCH = dict(Exposed="", Conditional="....", Transitive="xxxx", Resistant="////", NA="")

def apply():
    mpl.rcParams.update({
        "font.family": "serif",
        "font.serif": ["Liberation Serif", "DejaVu Serif"],
        "mathtext.fontset": "stix",
        "font.size": 8.2,
        "axes.titlesize": 8.8, "axes.labelsize": 8.2,
        "xtick.labelsize": 7.4, "ytick.labelsize": 7.4,
        "axes.edgecolor": INK2, "axes.linewidth": 0.6,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.facecolor": SURF, "figure.facecolor": SURF,
        "axes.grid": False,
        "xtick.color": INK2, "ytick.color": INK2,
        "text.color": INK, "axes.labelcolor": INK,
        "xtick.major.size": 2.5, "ytick.major.size": 2.5,
        "xtick.major.width": 0.6, "ytick.major.width": 0.6,
        "legend.frameon": False, "legend.fontsize": 7.4,
        "figure.dpi": 150, "savefig.dpi": 300,
        "savefig.bbox": "tight", "savefig.pad_inches": 0.02,
        "pdf.fonttype": 42, "ps.fonttype": 42,
    })
