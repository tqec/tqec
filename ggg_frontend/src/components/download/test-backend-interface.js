// Functions to communicate with the Python backend

import axios from 'axios';

/////////////////////////////////////////////////////////////

export function postExample(url, data) {
  console.log(url);
  console.log(data);
  axios({
    method: 'POST',
    url,
    data: JSON.stringify(data),
    headers: {
      'Content-Type': 'application/json',
    },
  })
    .then((response) => { console.log(response.status); })
    .catch((err) => { console.log(err); });
}

export function getExample(url, templateName = '2x2k') {
  return axios({
    method: 'GET',
    url,
    headers: {
      'Content-Type': 'application/json',
      'Data-Type': 'json',
    },
    responseType: 'json',
    params: {
      template_name: templateName
    }
  })
    .then((response) => {
      console.log(response.status);
      console.log(response.data.value);
      return response.data; // Return the received data
    })
    .catch((err) => { console.log(err); });
}
