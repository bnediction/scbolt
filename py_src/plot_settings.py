#!/usr/bin/python3

import matplotlib as mpl
import cycler, py_src.color_settings as color

mpl.style.use("default")

font = {"family" : "normal",
        "weight" : "normal",
        "size"   : 12}
mpl.rc("font", **font)

mpl.rcParams["text.usetex"] = True

mpl.rcParams["lines.linewidth"] = 1.5

margin = 0
mpl.rcParams.update({
    "axes.spines.top"    : False,
    "axes.spines.bottom" : True,
    "axes.spines.left"   : True,
    "axes.spines.right"  : False
})
mpl.rcParams["axes.xmargin"] = margin
mpl.rcParams["axes.ymargin"] = margin
mpl.rcParams["axes.zmargin"] = margin
mpl.rcParams["axes.labelsize"] = 14
mpl.rcParams["axes.prop_cycle"] = cycler.cycler(color=[
    color.blue,
    color.red,
    color.green,
    color.orange,
    color.purple,
    color.skyblue,
    color.teal,
    color.pink,
    color.violet,
    color.darkblue
])
