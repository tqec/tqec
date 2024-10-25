// formattedInfoTab.js
const formattedInfoTabContent = (
  <div style={{textAlign: 'center', marginTop: '40px'}}>
    <p>Welcome to the TQEC app!</p>
    <a
      className="App-link"
      href="https://github.com/QCHackers/tqec"
      target="_blank"
      rel="noopener noreferrer"
    >
      TQEC repo
    </a>
    <p>We designed it to facilitate prototyping quantum error correcting codes.</p>
    <ul style={{ listStylePosition: 'inside', paddingLeft: '0' }}>
      <li style={{ paddingLeft: '116px', marginTop: '20px' }}>
        Select tab 'Compose library' to create a library of plaquette and associate a circuit to each of them.<br />
        <span style={{ paddingLeft: '20px' }}>Each plaquette represents a 'type' of stabilizer-measurement circuit available to the QEC code or the templates.</span>
      </li>
      <li style={{ paddingLeft: '0px', marginTop: '20px' }}>
        [OLD] Select tab 'Create code' to stitch together the plaquettes and build the QEC code.
      </li>
      <li style={{ paddingLeft: '0px', marginTop: '20px' }}>
        Select tab 'Populate template' to fill a template (from the backend) with the plaquette from the library.
      </li>
    </ul>
  </div>
);

export default formattedInfoTabContent;
