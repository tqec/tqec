import { useApp } from '@pixi/react'
import { useState, useEffect } from 'react'
import { Container, Graphics, Text, TextStyle } from 'pixi.js'

// From the implementation of the tab 'library'
import { makeGrid } from '../tab_library/grid'
import Position from '../tab_library/position'
import { button } from '../tab_library/button'
import { Qubit } from '../tab_library/qubit'
import Plaquette from '../tab_library/plaquette'
import { savedPlaquettes, libraryColors } from '../tab_library'

// From the implementation of the tab 'code'
import PlaquetteType from '../tab_code/plaquette-type'

// From the main src folder
import { GRID_SIZE_TEMPLATE_WORKSPACE, GUIDE_TOP_LEFT_CORNER_TEMPLATE_WORKSPACE } from '../constants'
import { drawSquareFromTopLeft } from '../utils/graphics-utils'
import { copyPlaquette } from '../utils/plaquette-manipulation'

// From the implementation of the components
import config from '../components/download/config'
import { postExample, getExample } from '../components/download/test-backend-interface'

/////////////////////////////////////////////////////////////

let topLeftCornersOfPlaquettesInTemplateByLabel = {};

/////////////////////////////////////////////////////////////

export default function TqecTemplates({ selectedTemplate }) {
	useEffect(() => {
		// Handle the change of the selected template here
		console.log(`Selected template in TqecTemplates: ${selectedTemplate}`);
		// Add your logic to handle the selected option change in TqecTemplates
	}, [selectedTemplate]);

	// Initialize the app
	let app = useApp();

	// Remove all children from the stage to avoid rendering issues
	app.stage.removeChildren();
	const gridSize = GRID_SIZE_TEMPLATE_WORKSPACE;
	const qubitRadius = 7;
	document.getElementById('dxCell').value = 2;
	document.getElementById('dyCell').value = 2;
	let plaquetteDx = parseInt(document.getElementById('dxCell').value);
	let plaquetteDy = parseInt(document.getElementById('dyCell').value);

	// Create the workspace
	const workspace = new Container();
	workspace.name = 'workspace-template';

	// Create the grid container
	const grid = makeGrid(app, gridSize);
	// We want the grid to be in the lowest layer
    workspace.addChildAt(grid, 0);

/////////////////////////////////////////////////////////////

	// Add guide for the eyes for the plaquette boundaries.
	// They are located via the position of the top, left corner.
	// The first guide is where the plaquette is built, the other guides are for the library.
	const guideTopLeftCorner = GUIDE_TOP_LEFT_CORNER_TEMPLATE_WORKSPACE;
	let libraryTopLeftCorners = [[21, 3], [21, 7], [21, 11], [21, 15]];
	const outline = new Graphics();
	outline.clear();
	outline.lineStyle(2, 'lightcoral');
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

	const testButton = button('test of API to interface with API', gridSize, 1*gridSize, 'orange', 'black');
	workspace.addChild(testButton);

	const getButton = button('GET template from backend', gridSize, 2*gridSize, 'white', 'black');
	workspace.addChild(getButton);

    // Custom Hook to handle response data
    function useResponseData(responseData) {
        useEffect(() => {
            if (responseData) {
                console.log('Using response data:', responseData);
				// Select the template to fill.
				const templateData = responseData.templates.find(item => item.name === selectedTemplate);
				const instantiation = templateData.instantiation;

				topLeftCornersOfPlaquettesInTemplateByLabel = {};
				// Iterate through the outer array
				const style = new TextStyle({fontSize: 36, fill: 'red'});
				for (let i = 0; i < instantiation.length; i++) {
					// Get the current inner array
					const innerArray = instantiation[i];

					// Iterate through the inner array
					for (let j = 0; j < innerArray.length; j++) {
						// Add workspace guidelines according to the dimensions in the received json data.
						const y0 = guideTopLeftCorner.y + i * plaquetteDy;
						const x0 = guideTopLeftCorner.x + j * plaquetteDx;
						drawSquareFromTopLeft(outline, {x: x0*gridSize, y: y0*gridSize}, plaquetteDx*gridSize, plaquetteDy*gridSize)
						// Check if the value is 1 or 2
						const label = innerArray[j];
						let digit = new Text(label.toString(), style);
						digit.x = x0*gridSize;
						digit.y = y0*gridSize;
						if (!topLeftCornersOfPlaquettesInTemplateByLabel.hasOwnProperty(label)) {
						    topLeftCornersOfPlaquettesInTemplateByLabel[label] = []; // Initialize with an empty array
						}
						topLeftCornersOfPlaquettesInTemplateByLabel[label].push({x: x0 - guideTopLeftCorner.x, y: y0 - guideTopLeftCorner.y});
						outline.addChild(digit);
					}
				}
            } else {
                console.warn('WARNING: No data received yet.');
            }
        }, [responseData]); // Trigger effect when responseData changes
    }

    // State to hold response data
    const [responseData, setResponseData] = useState(null);

	getButton.on('click', (_e) => {
		let url = '/example'
		const localTesting = !window.location.href.includes('https://'); // FIXME: this is a hack
		let backendURL = `${localTesting
		  ? `http://${config.devBackendURL.ip}:${config.devBackendURL.port}`
		  : config.prodBackendURL
		}`;
		backendURL += url;

		// Using the promise approach:
		// getExample returns the data (in json format) which are handled using promises
		// like `.then()` and `.catch()` in the calling de.
		const templateName = 'library';
		getExample(backendURL, templateName)
			.then(data => {
                setResponseData(data); // Update state with response data
				// Example: Display received data in an HTML element
				const resultDiv = document.getElementById('result');
				resultDiv.textContent = JSON.stringify(data, null, 2);
            })
            .catch(error => {
                console.error('ERROR while fetching data:', error);
            });
	});

	// Use custom Hook to handle response data
    useResponseData(responseData);

/////////////////////////////////////////////////////////////

	const infoButton = button('Library of plaquettes', libraryTopLeftCorners[0][0]*gridSize, 1*gridSize, 'orange', 'black');
	workspace.addChild(infoButton);

    // Select the qubits that are part of a plaquette
	const importPlaquettesButton = button('Import plaquettes from composer', gridSize, 4*gridSize, 'white', 'black');
	workspace.addChild(importPlaquettesButton);

    importPlaquettesButton.on('click', (_e) => {
		plaquetteDx = parseInt(document.getElementById('dxCell').value);
		plaquetteDy = parseInt(document.getElementById('dyCell').value);
		libraryTopLeftCorners = [[21, 3], [21, 3+plaquetteDy+2], [21, 3+(plaquetteDy+2)*2], [21, 3+(plaquetteDy*2)*3]]
		// Add library guidelines.
		for (const [x0, y0] of libraryTopLeftCorners) {
			drawSquareFromTopLeft(outline, {x: x0*gridSize, y: y0*gridSize}, plaquetteDx*gridSize, plaquetteDy*gridSize)
		}
		// Add library plaquettes.
		//const library_workspace = document.getElementsByName('workspace-library');
		let plaquetteTypes = [];
		//const numPlaquettes = savedPlaquettes.length;
		savedPlaquettes.forEach((plaq, index) => {
			if (plaq.name !== 'WIP plaquette') {
				console.log('INFO: plaquette name:', plaq.name)
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
	const undoButton = button('Remove last plaquette', gridSize, 6*gridSize, 'white', 'black');
	workspace.addChild(undoButton);

    undoButton.on('click', (_e) => {
		if (workspace.children[num_background_children] instanceof Plaquette
			&& !(workspace.children[num_background_children] instanceof PlaquetteType) ) {
			workspace.removeChildAt(num_background_children);
		}
	});

/////////////////////////////////////////////////////////////

    // Confirm and fully populate the template.
	const fillButton = button('Fill the template', gridSize, 15*gridSize, 'white', 'black');
	workspace.addChild(fillButton);
	let childAssignedByLabel = {};

    fillButton.on('click', (_e) => {
		// Search among the children the Plaquettes.
		// Identify the plaquette occupy the cell with label 1 and 2.
		let childAssignedByLabel_ = {};
	    for (let i = 0; i < workspace.children.length; i++) {
	        const child = workspace.children[i];
	        if (child instanceof Plaquette
				&& !(child instanceof PlaquetteType) ) {
				const pos = child.topLeftCorner
				console.log('INFO:', child.name, '  coords:', pos.x, pos.y )
				Object.entries(topLeftCornersOfPlaquettesInTemplateByLabel).forEach(([label, array]) => {
					const doesLabelMatch = array.some(item => item.x === pos.x && item.y === pos.y);
    				if (doesLabelMatch) {
						if (!childAssignedByLabel_.hasOwnProperty(label)) {
							childAssignedByLabel_[label] = i;
						} else {
							console.error('ERROR: Only one plaquette should be associated with label', label, 'in the template');
						}
					}
				});
	        }
	    }
		childAssignedByLabel = childAssignedByLabel_;
		// Fill all cells of template.
		Object.entries(childAssignedByLabel).forEach(([label, child_id]) => {
			const model = workspace.children[child_id]
			topLeftCornersOfPlaquettesInTemplateByLabel[label].forEach(tl => {
    			// If no child of type plaquette exist at that location, add plaquette.
				const existPlaquette = workspace.children.some(child => child instanceof Plaquette && child.topLeftCorner.x === tl.x && child.topLeftCorner.y === tl.y);
				console.log('INFO: top-left ', tl, ' --> exist plaquette?', existPlaquette);
				if (!existPlaquette) {
					let translate = {x: tl.x - model.topLeftCorner.x, y: tl.y - model.topLeftCorner.y}; // in GRID_SIZE
					const copy = copyPlaquette(model, translate, GRID_SIZE_TEMPLATE_WORKSPACE, GUIDE_TOP_LEFT_CORNER_TEMPLATE_WORKSPACE)
            		workspace.addChild(copy);
				}
			});
		});
	});

/////////////////////////////////////////////////////////////

	// Create a button to de-select all qubits
	const postButton = button('POST the filled template to backend', gridSize, 17*gridSize, 'white', 'black');
	workspace.addChild(postButton);

	postButton.on('click', (_e) => {
		let url = '/example'
		const localTesting = !window.location.href.includes('https://'); // FIXME: this is a hack
		let backendURL = `${localTesting
		  ? `http://${config.devBackendURL.ip}:${config.devBackendURL.port}`
		  : config.prodBackendURL
		}`;
		backendURL += url;

		const payload = { name: 'filled_' + selectedTemplate, plaquettes: []};
		Object.entries(childAssignedByLabel).forEach(([label, child_id]) => {
		    payload.plaquettes.push({ label: parseInt(label), pname: workspace.children[child_id].name });
		});
		postExample(backendURL, payload);
	});

/////////////////////////////////////////////////////////////

    //  Add workspace to the stage
    workspace.visible = true;
	app.stage.addChild(workspace);

    return null;
}
