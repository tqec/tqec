import { useApp } from '@pixi/react'
import { makeGrid } from '../library/grid'
import { Container, Graphics } from 'pixi.js'
import { Qubit } from '../library/qubit'
import Position from '../library/position'
import { button } from '../library/button'
//import Plaquette from '../library/plaquette'
import Circuit from '../library/circuit'

//import addListenersToTabButtons from './TEMP_addListener'

/////////////////////////////////////////////////////////////

export default function TqecCode() {
	// Initialize the app
	let app = useApp();

	// Remove all children from the stage to avoid rendering issues
	app.stage.removeChildren();
	const gridSize = 50;
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
	const guideTopLeftCorner = [3, 3]
	let libraryTopLeftCorners = [[21, 3], [21, 7], [21, 11], [21, 15]]
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
    		pos.on('click', (_e) => {
				const qubit = new Qubit(x*gridSize, y*gridSize, qubitRadius);
				// Name the qubit according to its position relative to the top-left
				// corner of the plaquette-building area.
				qubit.name = `Q(${String(x-guideTopLeftCorner[0]).padStart(2, ' ')},${String(y-guideTopLeftCorner[1]).padStart(2, ' ')})`;
				qubit.interactive = true;
				qubit.on('click', qubit.select)
				qubit.select()
				workspace.addChild(qubit);
			});
			workspace.addChild(pos);
		}
	}
	//const num_background_children = workspace.children.length;

/////////////////////////////////////////////////////////////

	const infoButton = button('Library of plaquettes', libraryTopLeftCorners[0][0]*gridSize, 1*gridSize, 'orange', 'black');
	workspace.addChild(infoButton);

    // Select the qubits that are part of a plaquette 
	const importPlaquettesButton = button('Import plaquettes from composer', gridSize, 1*gridSize, 'white', 'black');
	workspace.addChild(importPlaquettesButton);
	let savedPlaquettes = [];

    importPlaquettesButton.on('click', (_e) => {
		outline.clear()
		plaquetteDx = parseInt(document.getElementById('dxCell').value);
		plaquetteDy = parseInt(document.getElementById('dyCell').value);
		libraryTopLeftCorners = [[21, 3], [21, 3+plaquetteDy+2], [21, 3+(plaquetteDy+2)*2], [21, 3+(plaquetteDy*2)*3]]
		outline.lineStyle(2, 'lightcoral');
		// Add workspace
		let y0 = guideTopLeftCorner[1];
		while (y0 + plaquetteDy < 19) {
			let x0 = guideTopLeftCorner[0];
			while (x0 + plaquetteDx < libraryTopLeftCorners[0][0] && y0 + plaquetteDy < 19) {
				const x1 = x0 + plaquetteDx;
				const y1 = y0 + plaquetteDy;
				outline.moveTo(x0*gridSize, y0*gridSize);
				outline.lineTo(x1*gridSize, y0*gridSize);
				outline.lineTo(x1*gridSize, y1*gridSize);
				outline.lineTo(x0*gridSize, y1*gridSize);
				outline.lineTo(x0*gridSize, y0*gridSize);
				x0 += plaquetteDx;
			}
			y0 += plaquetteDy;
		}
		// Add library
		for (const [x0, y0] of libraryTopLeftCorners) {
			const x1 = x0 + plaquetteDx;
			const y1 = y0 + plaquetteDy;
			outline.moveTo(x0*gridSize, y0*gridSize);
			outline.lineTo(x1*gridSize, y0*gridSize);
			outline.lineTo(x1*gridSize, y1*gridSize);
			outline.lineTo(x0*gridSize, y1*gridSize);
			outline.lineTo(x0*gridSize, y0*gridSize);
		}
	});

/////////////////////////////////////////////////////////////

	// Create a button to de-select all qubits 
	const downloadCodeButton = button('Download QEC code', gridSize, 19*gridSize, 'white', 'black');
	workspace.addChild(downloadCodeButton);

	downloadCodeButton.on('click', (_e) => {
		if (savedPlaquettes.length === 0) return;
	
		let message = '';
		// Add info on cell size
		message += 'This is the complete QEC code.\n'
		let counter = 0;
		savedPlaquettes.forEach((plaq) => {
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