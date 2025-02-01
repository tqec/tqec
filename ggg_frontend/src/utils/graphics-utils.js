// Utility functions used by the frontend

import { Graphics } from 'pixi.js'

/////////////////////////////////////////////////////////////
// Creation of the red guidelines for the rectangular cells.

export function drawSquareFromTopLeft(outline, position, dx, dy) {
    if (!(outline instanceof Graphics)) {
        return;
    }
    outline.moveTo(position.x, position.y);
    outline.lineTo(position.x + dx, position.y);
    outline.lineTo(position.x + dx, position.y + dy);
    outline.lineTo(position.x, position.y + dy);
    outline.lineTo(position.x, position.y);
    return
}
