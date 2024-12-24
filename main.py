from tqec.plaquette.rpng import RPNGDescription
from tqec.templates.viz_rpng import rpng_svg_viewer

des = RPNGDescription.from_string(
    "---- -z2- -z3- -z4-",
)

svg = rpng_svg_viewer(des)

print(svg, file=open("rpng.svg", "w"))
