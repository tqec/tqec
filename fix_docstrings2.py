import re

def fix_file(filename):
    with open(filename, 'r') as f:
        content = f.read()

    # Apply fixes
    content = content.replace("more efficient by manipulating text files directly without creating ``BlockGraph`` objects.", "more efficient by manipulating text files directly\nwithout creating ``BlockGraph`` objects.")
    content = content.replace("visual coordinate scaling factor--it has no meaning inside the compiler. It serves for 3D tools (primarily ``SketchUp``) to store positions in a visual coordinate space where blocks are separated by visible pipe gaps.", "visual coordinate scaling factor--it has no meaning inside the compiler.\n    It serves for 3D tools (primarily ``SketchUp``) to store positions in a visual coordinate\n    space where blocks are separated by visible pipe gaps.")

    with open(filename, 'w') as f:
        f.write(content)

fix_file('src/tqec/interop/converters.py')
fix_file('src/tqec/interop/shared.py')
