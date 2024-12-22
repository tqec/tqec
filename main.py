from tqec.templates.indices.display import display_template_from_instantiation
from tqec.templates.indices.qubit import QubitSpatialJunctionTemplate

template = QubitSpatialJunctionTemplate()
array = template.instantiate(2)
print(array)
display_template_from_instantiation(array)
