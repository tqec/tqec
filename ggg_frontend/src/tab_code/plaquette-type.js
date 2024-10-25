// Define class Plaquette and its methods

import { Container } from 'pixi.js'

// From the implementation of the tab 'library'
import Position from '../tab_library/position';
import Plaquette from '../tab_library/plaquette';

// From the main src folder
import { GRID_SIZE_CODE_WORKSPACE, GUIDE_MAX_BOTTOM_RIGHT_CORNER_CODE_WORKSPACE, GUIDE_TOP_LEFT_CORNER_CODE_WORKSPACE } from '../constants';
import { GRID_SIZE_TEMPLATE_WORKSPACE, GUIDE_TOP_LEFT_CORNER_TEMPLATE_WORKSPACE } from '../constants';
import { copyPlaquette } from '../utils/plaquette-manipulation';

/////////////////////////////////////////////////////////////

/**
 * Plaquette class
 * @extends Graphics
 * @constructor
 * @param {array} qubits - The qubits which are part of the plaquette
 * @param {color} color - Color filling of the plaquette
 * @param {num_background_children} num_background_children - Used to place the latest plaquette on top of the workspace background but below every other elements
 * @param {base_translate_vector} base_translate_vector - Used to confirm that the latest plaquette is snapped to a cell
 */
export default class PlaquetteType extends Plaquette {
    constructor(qubits, color = 'purple', topLeftCorner = null, num_background_children = -1, base_translate_vector = {x:0, y:0}) {
        super(qubits, color, topLeftCorner);
        this.add_at = num_background_children;
        this.base_translate_vector = base_translate_vector;
        this.interactive = true;
        this.buttonMode = true;
        this.on('pointerdown', this.onDragStart)
            .on('pointerup', this.onDragEnd)
            .on('pointerupoutside', this.onDragEnd)
            .on('pointermove', this.onDragMove);

        // Store initial drag position
        this.dragging = false;
        this.dragData = null;
        this.startPosition = { x: 0, y: 0 };
    };

	/**
	 * Implementation of the behavior when the plaquettes are dragged
	 */
    onDragStart(event) {
        // Store initial drag position
        this.dragging = true;
        this.dragData = event.data;
        this.startPosition = this.dragData.getLocalPosition(this.parent);
        this.alpha = 0.5;
    }

    onDragMove() {
        if (this.dragging) {
            const newPosition = this.dragData.getLocalPosition(this.parent);
            this.x = newPosition.x - this.startPosition.x;
            this.y = newPosition.y - this.startPosition.y;
        }
    }

    onDragEnd() {
        this.dragging = false;
        this.alpha = 1;

        // Determine reference positions depending on the parent workspace.
        let GRID_SIZE = GRID_SIZE_CODE_WORKSPACE;
        let GUIDE_MAX_BOTTOM_RIGHT_CORNER = GUIDE_MAX_BOTTOM_RIGHT_CORNER_CODE_WORKSPACE;
        let GUIDE_TOP_LEFT_CORNER = GUIDE_TOP_LEFT_CORNER_CODE_WORKSPACE;
        if (this.parent.name === 'workspace-template') {
            GRID_SIZE = GRID_SIZE_TEMPLATE_WORKSPACE;
            GUIDE_TOP_LEFT_CORNER = GUIDE_TOP_LEFT_CORNER_TEMPLATE_WORKSPACE;
        }

        // Find the closest position to the first qubit.
        // Use it to compute the expected translation vector.
        let temp_x = this.qubits[0].globalX + this.x;
        let temp_y = this.qubits[0].globalY + this.y;
        let min_distance = 10000;
        let translate_x = 0;
        let translate_y = 0;
	    this.parent.children.forEach((child) => {
	        if (child instanceof Position) {
                const d = (temp_x-child.globalX)**2 + (temp_y-child.globalY)**2;
                if (d < min_distance) {
                    min_distance = d;
                    translate_x = child.globalX - this.qubits[0].globalX;
                    translate_y = child.globalY - this.qubits[0].globalY;
                }
            }
        });
        // If the translator vector does not lead to a cell, log an error and return.
		const plaquetteDx = parseInt(document.getElementById('dxCell').value);
		const plaquetteDy = parseInt(document.getElementById('dyCell').value);
        // Horizontally aligned with a cell.
        let is_valid_translation = (translate_x/GRID_SIZE - this.base_translate_vector.x) % plaquetteDx === 0;
        // Vertically aligned with a cell.
        is_valid_translation = is_valid_translation && (translate_y/GRID_SIZE - this.base_translate_vector.y) % plaquetteDy === 0;
        // Horizontally within the cells in the guide.
        is_valid_translation = is_valid_translation && (translate_x/GRID_SIZE - this.base_translate_vector.x) + plaquetteDx <= GUIDE_MAX_BOTTOM_RIGHT_CORNER.x - GUIDE_TOP_LEFT_CORNER.x;
        is_valid_translation = is_valid_translation && (translate_x/GRID_SIZE - this.base_translate_vector.x) >= 0;
        // Vertically within the cells in the guide.
        is_valid_translation = is_valid_translation && (translate_y/GRID_SIZE - this.base_translate_vector.y) + plaquetteDy <= GUIDE_MAX_BOTTOM_RIGHT_CORNER.y - GUIDE_TOP_LEFT_CORNER.y;
        is_valid_translation = is_valid_translation && (translate_y/GRID_SIZE - this.base_translate_vector.y) >= 0;
		// FIXME: Check that the cell is still "free".
        if ( is_valid_translation === false ) {
            console.warn('WARNING: Wrong translation for plaquette -> rejected')
            // Reset the position of the original plaquette
            this.x = 0;
            this.y = 0;
            return;
        }

        // Check that the parent is a workspace, either code or template.
        if (!(this.parent instanceof Container)) {
            console.error('ERROR: The parent of a PlaquetteType should be a Container');
            return;
        }
        // Create a copy of the plaquette at the current position.
        const copy = copyPlaquette(this, {x: translate_x/GRID_SIZE, y: translate_y/GRID_SIZE}, GRID_SIZE, GUIDE_TOP_LEFT_CORNER);
        // Add to the parent workspace.
        if (this.add_at >= 0) {
            this.parent.addChildAt(copy, this.add_at);
        }

        // Reset the position of the original plaquette
        this.x = 0;
        this.y = 0;

        // If the PlaquetteType was dragged in the code tab, update the compact
        // representation of the QEC code. Otherwise return.
        if (this.parent.name !== 'workspace-code') {
            return;
        }
        // Update the compact representation of the QEC code.
        const codesummary = document.getElementById('codeSummary');
        let message = codesummary.value.split('\n');
        let lines = message;
		// Recall that plaquette names are like "plaquette 12", starting from "plaquette 1"
		const plaquette_id = parseInt(this.name.match(/\d+/)[0]);
        const col = (translate_x/GRID_SIZE - this.base_translate_vector.x) / plaquetteDx;
        const row = (translate_y/GRID_SIZE - this.base_translate_vector.y) / plaquetteDy;
        // TODO: Here we assume that there is a single space before every plaquette id is left padded with spaces
        console.log('INFO from plaquette-type:', row, col)
        let modifiedLine = lines[row].substring(0, 3*col) + `${String(plaquette_id).padStart(3, ' ')}` + lines[row].substring(3*col+3);
        lines[row] = modifiedLine;
        codesummary.value = lines.join('\n');
    }

}
