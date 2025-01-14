import logo from './tqec_logo.svg';
import './App.css';
import {Stage} from '@pixi/react'
import React, { useState } from 'react';
import DropdownMenu from './dropdown';

// Implementation of the workspace of the various tabs.
import TqecLibrary from './tab_library'
import TqecCode from './tab_code'
import TqecTemplates from './tab_template'
import formattedInfoTabContent from './formattedInfoTab';

/* The logo has been created as the SVG rendering of the ASCII:
 *
 *    /---/  //---/    //---/   //---/
 *     //   //   /    //-/     //
 *    //   //---/==  //---/   //---/
 *
 *  with the web app: https://ivanceras.github.io/svgbob-editor/
 */

const handleTabClick = (tabId) => {
   // Hide all tab contents
  const tabContents = document.querySelectorAll('.Tab-content');
  tabContents.forEach(content => {
      content.style.display = 'none';
  });

  // Show the clicked tab content
  const clickedTabContent = document.getElementById(`content${tabId}`);
  if (clickedTabContent) {
      clickedTabContent.style.display = 'block';
  }

  // Optionally, you can perform additional actions when a tab is clicked
  console.log(`Tab ${tabId} clicked`);
};

function App() {
  // Variable and method to react to a change of state.
  // In this case to the dropdown menu in tab 4, selecting
  // which template the user wants to fill.
  const [selectedOption, setSelectedOption] = useState(null);

  // Expected behavior when the template is selected in tab 4.
  const handleSelect = (value) => {
    setSelectedOption(value);
    console.log('INFO: from App.js, selected option:', value);
  };

  return (
    <div className="App">
      <header className="App-header">
        <img src={logo} className="App-logo" alt="logo" />
      </header>

      <div className="Tabs">
        <button className="Tab-button" id="tab1" onClick={() => handleTabClick(1)}>Info</button>
        <button className="Tab-button" id="tab2" onClick={() => handleTabClick(2)}>Compose library</button>
        <button className="Tab-button" id="tab3" onClick={() => handleTabClick(3)}>Create code</button>
        <button className="Tab-button" id="tab4" onClick={() => handleTabClick(4)}>Populate template</button>
        {/* -- Add more tabs as needed -- */}
      </div>

      <div id="Tab-content">
        <div id="content1" className="Tab-content active">
          {/*-- Content for Tab 1 -- */}
          {formattedInfoTabContent}
        </div>

        <div id="content2" className="Tab-content">
          {/*-- Content for Tab 2 -- */}

          <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center'}}>
            <p className="Comment-paragraph">Enter file name:</p>
            <input className="Cell-size"
              type="number"
              id="dxCell"
              placeholder="2"
            />
            <p className="Comment-paragraph">x</p>
            <input className="Cell-size"
              type="number"
              id="dyCell"
              placeholder="2"
            />
          </div>

          <Stage width={1400} height={900} options={{backgroundColor: "rgb(154, 193, 208)", antialias: true}}>
            <TqecLibrary />
          </Stage>

          <p className="Comment-paragraph">Circuit-editing area:</p>
          <div style={{ display: 'flex', justifyContent: 'center' }}>
            <textarea
              className="Text-area"
              type="text"
              id="editableCircuitArea"
              placeholder="Edit the circuit here..."
            />
          </div>
        </div>

        <div id="content3" className="Tab-content">
          {/*-- Content for Tab 3 -- */}
          <Stage width={1400} height={1100} options={{backgroundColor: 'rgb(157, 191, 145)', antialias: true}}>
            <TqecCode />
          </Stage>

          <p className="Comment-paragraph">Compact representation of the QEC code:</p>
          <div style={{ display: 'flex', justifyContent: 'center' }}>
            <textarea
              className="Text-area"
              type="text"
              id="codeSummary"
              placeholder="Code will appear here..."
            />
          </div>
        </div>

        <div id="content4" className="Tab-content">
          {/*-- Content for Tab 4 -- */}
          {/* Dropdown Menu Component */}
          <div style={{ display: 'flex', justifyContent: 'center' }}>
            <p className="Comment-paragraph">Select the template:</p>
            <DropdownMenu onSelect={handleSelect} />
          </div>
          <Stage width={1400} height={900} options={{backgroundColor: 'rgb(225, 193, 110)', antialias: true}}>
            {/* Pass the selectedOption to TqecApp */}
            <TqecTemplates selectedTemplate={selectedOption}/>
          </Stage>

          <pre id="result"></pre>
        </div>

        {/*-- Add more content areas as needed -- */}
      </div>
    </div>
  );
}

export default App;
