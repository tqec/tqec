import { Text, Container, Graphics } from 'pixi.js';

/////////////////////////////////////////////////////////////

/**
 * Create a button formed by a Text graphics plus a rounded rectangular background
 */
export const button = (text, x, y, buttonColor = 'black', fontColor = 'white', isLeftAligned = true) => {
	// Create the button container
	const button = new Container();

	// Create the button text
	const buttonText = new Text(text, {
		fontFamily: 'Arial',
		fontSize: 15,
		// Adjust the font size based on the width and height of the button
		fill: fontColor,
		align: 'center',
	});

	buttonText.x = x;
	buttonText.y = y;
	buttonText.anchor.set( (isLeftAligned) ? 0 : 0.5, 0.5);

	// Create the button background
	const buttonBackground = new Graphics();
	buttonBackground.beginFill(buttonColor);
	buttonBackground.drawRoundedRect(
		(isLeftAligned) ? buttonText.x - 15 : buttonText.x - buttonText.getBounds().width / 2 - 15,
		buttonText.y - buttonText.getBounds().height / 2 - 15,
		buttonText.getBounds().width + 30,
		buttonText.getBounds().height + 30
	);
	buttonBackground.endFill();

	// Add effects
	button.eventMode = 'static';
	// Add hover event
	button.on('pointerover', () => {
		buttonBackground.alpha = 0.8;
	});
	button.on('pointerout', () => {
		buttonBackground.alpha = 1;
	});

	// Apply cursor
	button.cursor = 'pointer';
	// Add the text to the button container
	button.addChild(buttonBackground);
	button.addChild(buttonText);

	// Add the button to the stage
	return button;
};
