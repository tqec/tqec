// Define functions to manipulate Plaquette objects

import Plaquette from '../tab_library/plaquette.js';
import { Qubit } from '../tab_library/qubit.js'

/**
 * Plaquette class
 * @param {Plaquette} plaquette - plaquette to copy
 * @param {Dict} translate - translate vector in units of gridSize (for the position of qubits and plaquette)
 * @param {float} gridSize - grid size (for the position of the qubits)
 * @param {Tuple} guideTopLeftCorner - position of the top-left corner of the guide/template in units of gridSize
 */
export function copyPlaquette(plaquette, translate, gridSize, guideTopLeftCorner) {
    // Create a copy of the plaquette at the current position.
    let qubits_of_copy = []
    plaquette.qubits.forEach((q) => {
        const qubit = new Qubit(q.globalX + translate.x * gridSize, q.globalY + translate.y * gridSize, q.radius);
        qubit.name = `Q(${String(qubit.globalX/gridSize - guideTopLeftCorner.x).padStart(2, ' ')},${String(qubit.globalY/gridSize - guideTopLeftCorner.y).padStart(2, ' ')})`;
        qubits_of_copy.push(qubit);
    });
    const copy = new Plaquette(qubits_of_copy, plaquette.color);
	copy.name = plaquette.name;
    copy.x += translate.x
    copy.y += translate.y
    copy._createConvexHull(0);
    copy.topLeftCorner = {x: translate.x + plaquette.topLeftCorner.x - guideTopLeftCorner.x,
                          y: translate.y + plaquette.topLeftCorner.y - guideTopLeftCorner.y}
    return copy;
}
