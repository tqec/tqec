import React, { useState, useEffect } from 'react';

import { getExample } from './components/download/test-backend-interface'
import config from './components/download/config'


const DropdownMenu = ({ onSelect }) => {
  const [options, setOptions] = useState([]);

  useEffect(() => {
		let url = '/example'
		const localTesting = !window.location.href.includes('https://'); // FIXME: this is a hack
		let backendURL = `${localTesting
		  ? `http://${config.devBackendURL.ip}:${config.devBackendURL.port}`
		  : config.prodBackendURL
		}`;
		backendURL += url;

		getExample(backendURL, 'library')
			.then(data => {
        setOptions(data.templates);
      })
      .catch(error => {
        console.error('Error fetching data:', error);
      });
  }, []);

  const handleChange = (event) => {
    onSelect(event.target.value);
  };

  return (
    <select
      style={{
        width: '150px',   // Specify the width of the dropdown
        height: '40px',   // Specify the height of the dropdown
        marginBottom: '20px',  // Space to be left empty below the dropdown
        padding: '10px'   // Padding inside the dropdown
      }}
      onChange={handleChange}
    >
      {options.map(option => (
        <option key={option.id} value={option.name}>
          {option.name}
        </option>
      ))}
    </select>
  );
};

export default DropdownMenu;
