// Define class Qubit and its methods

import { Graphics, Rectangle } from 'pixi.js'

/////////////////////////////////////////////////////////////

/**
 * Position class
 * @extends Graphics
 * @constructor
 * @param {number} x - The x position of the qubit
 * @param {number} y - The y position of the qubit
 * @param {number} radius - The radius of the circle representing the qubit
 */
export default class Position extends Graphics {
	constructor(x, y, radius = 5) {
		super();
		// Color properties (as static fields).
		Position.color = 'white'
		// UI properties
		this.eventMode = 'static';
		this.buttonMode = true;
		this.cursor = 'pointer';
		this.globalX = x;
		this.globalY = y;
		this.radius = radius;
		this.factor = 3; // TO expand the hitarea.
		this._createCircle(x, y, radius, Position.color);
	}

	_onPointerOver = () => {
		this.alpha = 0.5;
	};

	_onPointerOut = () => {
		this.alpha = 1;
	};

	/**
	 * Creates a circle
	 * @param {*} x
	 * @param {*} y
	 * @param {*} radius
	 * @param {*} color
	 */
	_createCircle(x, y, radius, color) {
		this.clear();
		// Create a circle
		this.beginFill(color);
		this.drawCircle(x, y, radius);
		this.endFill();

		// Add hover event
		this.on('pointerover', this._onPointerOver);
		this.on('pointerout', this._onPointerOut);

		// Enlarge the 'hit' area.
		const hit = new Rectangle(x-this.factor*radius, y-this.factor*radius, 2*this.factor*radius, 2*this.factor*radius)
		this.hitArea = hit;
	}
}
