global colour_green
global colour_blue
global colour_red
global colour_pink
global colour_violet
global colour_orchid
global colour_magenta
global colour_purple
global colour_indigo
global colour_slateblue
global colour_gray
global colour_darkgreen
global colour_yellow
global colour_gold
global colour_orange
global colour_darkorange
global colour_salmon
global colour_maroon
global colour_beet
global colour_teal
global colour_olive
global colour_limegreen
global colour_darkyellow
global colour_lightyellow
global colour_lightorange
global colour_black
global colour_lightgreen
global colour_coral
global colour_white
global colour_navy
global colour_darkblue
global colour_skyblue

def rgb(colour: list):
    return list(map(lambda x: x/255, colour))

colour_black       = rgb([  0,   0,   0])
colour_white       = rgb([255, 255, 255])
colour_blue        = rgb([  0,  20, 255])
colour_red         = rgb([255,  80,  50])
colour_green       = rgb([ 20, 200,  80])
colour_violet      = rgb([255,  51, 255])
colour_lightgreen  = rgb([ 20, 250,  80])
colour_coral       = rgb([255, 127,  80])
colour_yellow      = rgb([255, 255,   0])
colour_darkyellow  = rgb([204, 204,   0])
colour_lightyellow = rgb([128, 128,   0])
colour_darkorange  = rgb([255, 140,   0])
colour_lightorange = rgb([255, 165,  90])
colour_limegreen   = rgb([ 50, 255,  50])
colour_pink        = rgb([255, 182, 193])
colour_orchid      = rgb([218, 112, 214])
colour_magenta     = rgb([255,   0, 255])
colour_purple      = rgb([128,   0, 128])
colour_indigo      = rgb([ 75,   0, 130])
colour_slateblue   = rgb([ 71,  60, 139])
colour_gray        = rgb([112, 128, 144])
colour_darkgreen   = rgb([  0, 100,   0])
colour_gold        = rgb([238, 201,   0])
colour_orange      = rgb([255, 165,   0])
colour_salmon      = rgb([198, 113, 113])
colour_maroon      = rgb([128,   0,   0])
colour_beet        = rgb([142,  56, 142])
colour_teal        = rgb([ 56, 142, 142])
colour_olive       = rgb([142, 142,  56])
colour_navy        = rgb([  0,   0, 128])
colour_darkblue    = rgb([  0,   0, 139])
colour_skyblue     = rgb([135, 206, 235])