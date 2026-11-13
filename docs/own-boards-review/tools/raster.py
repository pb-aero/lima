import numpy as np
from PIL import Image, ImageDraw
RES = 0.025
def raster(layer, x0, y1, W, H, nets=None):
    """fill regions (optionally only given nets) + tracks + flashes of those nets into bool grid; origin top-left = (x0, y1)"""
    im = Image.new('1', (int(W/RES)+1, int(H/RES)+1), 0); d = ImageDraw.Draw(im)
    P = lambda x, y: ((x-x0)/RES, (y1-y)/RES)
    for r in layer['regions']:
        if nets is None or r['net'] in nets:
            if len(r['pts']) >= 3: d.polygon([P(*p) for p in r['pts']], fill=1)
    return np.array(im, dtype=bool)
def lookup(grid, x0, y1, x, y):
    i = int(round((y1-y)/RES)); j = int(round((x-x0)/RES))
    if 0 <= i < grid.shape[0] and 0 <= j < grid.shape[1]: return grid[i, j]
    return False
