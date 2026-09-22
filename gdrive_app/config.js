// The ONE thing you need to edit. Get this from Google Cloud Console after
// creating an OAuth Client ID (see README.md) - it looks like
// "123456789-abc123def456.apps.googleusercontent.com".
const CLIENT_ID = "205892015000-g6acepv1kof9amfjg5cg12cevoijqh88.apps.googleusercontent.com";

// The Google Drive folder this app creates and manages. Because the app
// only requests the narrow "drive.file" scope (not full Drive access), it
// can only ever see files/folders it created itself - so this whole
// structure gets created automatically the first time you sign in:
//
//   FavouriteThingsApp/
//     Music/<Genre>/<Album>/*.mp3 (+ optional metadata.json, cover.jpg)
//     radio_stations.json
const ROOT_FOLDER_NAME = "FavouriteThingsApp";

const RADIO_SEARCH_API = "https://de1.api.radio-browser.info/json/stations/search";

const el = (id) => document.getElementById(id);
