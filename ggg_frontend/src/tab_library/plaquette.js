// Define class Plaquette and its methods

import { Graphics } from 'pixi.js';
import { convexHull } from './utils'
import { Qubit } from './qubit'
import Circuit from './circuit'

/////////////////////////////////////////////////////////////

/**
 * Plaquette class
 * @extends Graphics
 * @constructor
 * @param {array} qubits - The qubits which are part of the plaquette
 * @param {Color} color - Color filling of the plaquette
 */
export default class Plaquette extends Graphics {
    constructor(qubits, color = 'purple', topLeftCorner = null) {
        super();
        this.color = color;
        this.qubits = qubits
		// UI properties
		this.buttonMode = true;
		this.cursor = 'pointer';
        //this.isDragging = false;
        //this.plaquetteMade = false;
        this.name = 'WIP plaquette';
        this.topLeftCorner = topLeftCorner;
        // Draw the plaquette
        // TODO: Only rectangular plaquettes, at the moment
        //this._createRectangle();
	    this._createConvexHull();
    };

	_onPointerOver = () => {
		this.alpha = 0.5;
	};

	_onPointerOut = () => {
		this.alpha = 1;
	};

	/**
	 * Creates a rectangle enclosing the qubits
	 */
	_createRectangle() {
        // Locate corners
        let xmin = 10000
        let xmax = 0
        let ymin = 10000
        let ymax = 0
        this.qubits.forEach(qubit => {
            let x = qubit.globalX;
            if (x < xmin) xmin = x;
            if (x > xmax) xmax = x;
            let y = qubit.globalY;
            if (y < ymin) ymin = y;
            if (y > ymax) ymax = y;
        });
		// Create a rectangle
		this.beginFill(this.color);
		this.drawRect(xmin, ymin, xmax-xmin, ymax-ymin);
		this.endFill();

		// Add hover event
		this.on('pointerover', this._onPointerOver);
		this.on('pointerout', this._onPointerOut);
	};

	/**
	 * Create the convex hull using the naive algorithm
     *
     * Start from a vertical line left to the qubits.
     * Then
	 */
	_createConvexHull(line_thickness = 10) {
        if (this.qubits.length === 0) return;
        // Convert the qubits in coordinate points
        let points = []
        this.qubits.forEach(qubit => {
            points.push({x: qubit.globalX, y: qubit.globalY});
        });
        const hull = convexHull(points)
        //console.log(`first point of the convex hull: (${hull[0].x}, ${hull[0].y})`)

        // Draw convex hull
		this.beginFill(this.color);
        this.lineStyle(line_thickness, this.color);
        this.moveTo(hull[0].x, hull[0].y);
        for (let i = 1; i < hull.length; i++) {
            this.lineTo(hull[i].x, hull[i].y);
        }
        this.lineTo(hull[0].x, hull[0].y);
		this.endFill();
	};

	/**
	 * Add circuit as child
	 */
    showCircuit() {
		this.children.forEach(child => {
			if (child instanceof Circuit) {
                if (child.visible === true) {
                    child.visible = false;
                } else {
                    child.visible = true;
                }
            }
        });
    };

    translatePlaquette(dx, dy) {
        // Move the qubits.
		this.qubits.forEach(q => {
            q.globalX += dx;
            q.globalY += dy;
		    if (q.role === 'none')
                q.changeColor(Qubit.color_none);
		    else if (q.role === 'x')
                q.changeColor(Qubit.color_x);
		    else if (q.role === 'z')
                q.changeColor(Qubit.color_z);
		    else if (q.role === 'a')
                q.changeColor(Qubit.color_a);
            q.updateLabel();
        });
        // Recompute the shaded area.
        this.clear();
	    this._createConvexHull();
    };

    /*
    onDragStart(event) {
        this.isDragging = true;
        this.initialPosition = event.data.getLocalPosition(this.parent);
        console.log(`Initial position: ${this.initialPosition}`);
    }
    */

}
