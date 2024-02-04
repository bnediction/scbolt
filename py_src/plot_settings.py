#!/usr/bin/python3

from typing import Optional

import cycler

import matplotlib as mpl, matplotlib.pyplot as plt
from matplotlib.axes._axes import Axes
from matplotlib.ticker import FormatStrFormatter
from matplotlib.colors import ListedColormap

import color_settings as colour

mpl.rcParams.update(mpl.rcParamsDefault)

font = {"family" : "normal",
        "weight" : "normal",
        "size"   : 12}
mpl.rc("font", **font)

mpl.rcParams["text.usetex"] = True
mpl.rcParams["lines.linewidth"] = 1.5

mpl.rcParams.update({
    "axes.spines.top"    : False,
    "axes.spines.bottom" : True,
    "axes.spines.left"   : True,
    "axes.spines.right"  : False
})

margin = 0
mpl.rcParams["axes.xmargin"] = margin
mpl.rcParams["axes.ymargin"] = margin
mpl.rcParams["axes.zmargin"] = margin
mpl.rcParams["axes.labelsize"] = 14

mpl.rcParams["axes.prop_cycle"] = cycler.cycler(color=[
    colour.blue,
    colour.red,
    colour.green,
    colour.orange,
    colour.purple,
    colour.skyblue,
    colour.teal,
    colour.pink,
    colour.violet,
    colour.darkblue
])

def set_default(
    ax: Optional[Axes] = None
    ):
        if ax is None:
            ax = plt.gca()
        
        ax.set_title("")
        ax.yaxis.set_major_formatter(FormatStrFormatter("%g"))
        ax.xaxis.set_major_formatter(FormatStrFormatter("%g"))
        return None

cmap = ListedColormap(
    colors  = colour.COLORS,
    name    = "default",
    N       = None
)

mpl.colormaps.register(cmap)