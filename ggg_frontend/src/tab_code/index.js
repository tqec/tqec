import { useApp } from '@pixi/react'
import { Container, Graphics } from 'pixi.js'

// From the implementation of the tab 'library'
import { makeGrid } from '../tab_library/grid'
import Position from '../tab_library/position'
import { button } from '../tab_library/button'
import Plaquette from '../tab_library/plaquette'
import Circuit from '../tab_library/circuit'
import { savedPlaquettes, libraryColors } from '../tab_library'
import { Qubit } from '../tab_library/qubit'

// From the implementation of the tab 'code'
import PlaquetteType from './plaquette-type'

// From the main src folder
import { GRID_SIZE_CODE_WORKSPACE, GUIDE_MAX_BOTTOM_RIGHT_CORNER_CODE_WORKSPACE, GUIDE_TOP_LEFT_CORNER_CODE_WORKSPACE } from '../constants'
import { drawSquareFromTopLeft } from '../utils/graphics-utils'

/////////////////////////////////////////////////////////////

export default function TqecCode() {
	// Initialize the app
	let app = useApp();

	// Remove all children from the stage to avoid rendering issues
	app.stage.removeChildren();
	const gridSize = GRID_SIZE_CODE_WORKSPACE;
	const qubitRadius = 7;
	document.getElementById('dxCell').value = 2;
	document.getElementById('dyCell').value = 2;
	let plaquetteDx = parseInt(document.getElementById('dxCell').value);
	let plaquetteDy = parseInt(document.getElementById('dyCell').value);

	// Create the workspace
	const workspace = new Container();
	workspace.name = 'workspace-code';

	// Create the grid container
	const grid = makeGrid(app, gridSize);
	// We want the grid to be in the lowest layer
    workspace.addChildAt(grid, 0);

/////////////////////////////////////////////////////////////

	// Add guide for the eyes for the plaquette boundaries.
	// They are located via the position of the top, left corner.
	// The first guide is where the plaquette is built, the other guides are for the library.
	const guideTopLeftCorner = GUIDE_TOP_LEFT_CORNER_CODE_WORKSPACE;
	let libraryTopLeftCorners = [[21, 3], [21, 7], [21, 11], [21, 15]];
	const outline = new Graphics();
	workspace.addChild(outline);

/////////////////////////////////////////////////////////////

	// Add qubit positions to the workspace
	for (let x = 0; x <= app.screen.width/gridSize; x += 1) {
		for (let y = 0; y <= app.screen.height/gridSize; y += 1) {
			// Skip every other qubit
            if ( (x+y) % 2 === 1 )
                continue;
			// Create a qubit
			const pos = new Position(x*gridSize, y*gridSize, qubitRadius-2);
			workspace.addChild(pos);
		}
	}
	const num_background_children = workspace.children.length;

/////////////////////////////////////////////////////////////

	const infoButton = button('Library of plaquettes', libraryTopLeftCorners[0][0]*gridSize, 1*gridSize, 'orange', 'black');
	workspace.addChild(infoButton);

    // Select the qubits that are part of a plaquette
	const importPlaquettesButton = button('Import plaquettes from composer', gridSize, 1*gridSize, 'white', 'black');
	workspace.addChild(importPlaquettesButton);
	let codePlaquettes = [];

    importPlaquettesButton.on('click', (_e) => {
		outline.clear()
		plaquetteDx = parseInt(document.getElementById('dxCell').value);
		plaquetteDy = parseInt(document.getElementById('dyCell').value);
		libraryTopLeftCorners = [[21, 3], [21, 3+plaquetteDy+2], [21, 3+(plaquetteDy+2)*2], [21, 3+(plaquetteDy*2)*3]]
		outline.lineStyle(2, 'lightcoral');
		// Add workspace guidelines.
		let y0 = guideTopLeftCorner.y;
		let message = '';
		while (y0 + plaquetteDy <= GUIDE_MAX_BOTTOM_RIGHT_CORNER_CODE_WORKSPACE.y) {
			let x0 = guideTopLeftCorner.x;
			while (x0 + plaquetteDx <= GUIDE_MAX_BOTTOM_RIGHT_CORNER_CODE_WORKSPACE.x) {
				drawSquareFromTopLeft(outline, {x: x0*gridSize, y: y0*gridSize}, plaquetteDx*gridSize, plaquetteDy*gridSize)
				x0 += plaquetteDx;
				message += '  .';
			}
			y0 += plaquetteDy;
			message += '\n';
		}
		// Add library guidelines.
		for (const [x0, y0] of libraryTopLeftCorners) {
			drawSquareFromTopLeft(outline, {x: x0*gridSize, y: y0*gridSize}, plaquetteDx*gridSize, plaquetteDy*gridSize)
		}
        // Create the compact representation of the (empty) QEC code
        const codesummary = document.getElementById('codeSummary');
        codesummary.value = message;
		// Add library plaquettes.
		//const library_workspace = document.getElementsByName('workspace-library');
		let plaquetteTypes = [];
		//const numPlaquettes = savedPlaquettes.length;
		savedPlaquettes.forEach((plaq, index) => {
			if (plaq.name !== 'WIP plaquette') {
				let qubits = [];
				plaq.qubits.forEach((q) => {
					const qubit = new Qubit(q.globalX, q.globalY, q.Radius);
					qubit.name = q.name;
					qubit.updateLabel();
					workspace.addChild(qubit);
					qubits.push(qubit);
				});
				// Recall that plaquette names are like "plaquette 12", starting from "plaquette 1"
				const plaquette_id = parseInt(plaq.name.match(/\d+/)[0]);
				const base_translate_vector = {x: guideTopLeftCorner.x - libraryTopLeftCorners[plaquette_id-1][0],
				                               y: guideTopLeftCorner.y - libraryTopLeftCorners[plaquette_id-1][1]};
				const p_type = new PlaquetteType(qubits, libraryColors[index], plaq.topLeftCorner, num_background_children, base_translate_vector)
				p_type.name = plaq.name;
				plaquetteTypes.push(p_type);
				workspace.addChildAt(p_type, num_background_children);
			}
		});
		// FIXME: Some plaquettes in the red-delimited space may already be there.
		//        Compose the compact representation of the code accordingly.
	});

/////////////////////////////////////////////////////////////

    // Undo button, meaning that the last plaquette added is removed.
	const undoButton = button('Remove last plaquette', gridSize, 2*gridSize, 'white', 'black');
	workspace.addChild(undoButton);

    undoButton.on('click', (_e) => {
		if (workspace.children[num_background_children] instanceof Plaquette
			&& !(workspace.children[num_background_children] instanceof PlaquetteType) ) {
			workspace.removeChildAt(num_background_children);
			// FIXME: correct the compact representation of the code!
		}
	});

/////////////////////////////////////////////////////////////

	// Create a button to de-select all qubits
	const downloadCodeButton = button('Download QEC code', gridSize, 21*gridSize, 'white', 'black');
	workspace.addChild(downloadCodeButton);

	downloadCodeButton.on('click', (_e) => {
		if (codePlaquettes.length === 0) return;

		let message = '';
		// Add info on cell size
		message += 'This is the complete QEC code.\n'
		let counter = 0;
		codePlaquettes.forEach((plaq) => {
			if (plaq.name !== 'WIP plaquette') {
				message += '###############\n'
				message += `# plaquette ${counter} #\n`
				message += '###############\n\n'
				plaq.children.forEach((child) => {
					if (child instanceof Circuit) {
						console.log('circuit to add');
						message += child.art.text;
						message += '\n\n\n';
						console.log(message);
					}
				});
				counter += 1;
			}
		});
		const blob = new Blob([message], { type: 'text/plain' });
		const url = URL.createObjectURL(blob);

		const link = document.createElement('a');
		link.href = url;
		link.download = 'qec_code.txt';
		document.body.appendChild(link);
		link.click();
		document.body.removeChild(link);
		URL.revokeObjectURL(url);
	});

/////////////////////////////////////////////////////////////

    //  Add workspace to the stage
    workspace.visible = true;
	app.stage.addChild(workspace);

    return null;
}
