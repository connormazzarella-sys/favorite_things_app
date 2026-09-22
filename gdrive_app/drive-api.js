// Low-level Google Drive helpers shared by every tab. Everything here
// assumes `accessToken` (a valid access token string) is already set by
// auth.js before any of these are called.

const DRIVE_FILES_URL = "https://www.googleapis.com/drive/v3/files";
const DRIVE_UPLOAD_URL = "https://www.googleapis.com/upload/drive/v3/files";
const FOLDER_MIME = "application/vnd.google-apps.folder";

function escapeDriveQueryValue(value) {
  return value.replace(/\\/g, "\\\\").replace(/'/g, "\\'");
}

// Finds a child of `parentId` by exact name (optionally restricted to
// folders), or creates it if missing. This is the core primitive the whole
// Genre -> Album folder structure is built from.
async function findOrCreateChild(parentId, name, isFolder) {
  const safeName = escapeDriveQueryValue(name);
  let q = `name='${safeName}' and '${parentId}' in parents and trashed=false`;
  if (isFolder) q += ` and mimeType='${FOLDER_MIME}'`;
  const listResp = await gapi.client.drive.files.list({ q, fields: "files(id,name)" });
  if (listResp.result.files && listResp.result.files.length > 0) {
    return listResp.result.files[0].id;
  }
  const createResp = await gapi.client.drive.files.create({
    resource: {
      name,
      mimeType: isFolder ? FOLDER_MIME : "application/octet-stream",
      parents: [parentId],
    },
    fields: "id",
  });
  return createResp.result.id;
}

// Lists the direct children of a folder. `isFolder` (true/false/undefined)
// optionally filters to just folders, just files, or everything.
async function listChildren(parentId, isFolder) {
  let q = `'${parentId}' in parents and trashed=false`;
  if (isFolder === true) q += ` and mimeType='${FOLDER_MIME}'`;
  if (isFolder === false) q += ` and mimeType!='${FOLDER_MIME}'`;
  const resp = await gapi.client.drive.files.list({ q, fields: "files(id,name,mimeType)", orderBy: "name" });
  return resp.result.files || [];
}

async function findChildByName(parentId, name) {
  const safeName = escapeDriveQueryValue(name);
  const q = `name='${safeName}' and '${parentId}' in parents and trashed=false`;
  const resp = await gapi.client.drive.files.list({ q, fields: "files(id,name)" });
  return (resp.result.files && resp.result.files[0]) || null;
}

async function fetchFileBlob(fileId) {
  const resp = await fetch(`${DRIVE_FILES_URL}/${fileId}?alt=media`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!resp.ok) throw new Error(`Couldn't fetch file (${resp.status})`);
  return resp.blob();
}

async function fetchFileText(fileId) {
  const blob = await fetchFileBlob(fileId);
  return blob.text();
}

async function fetchFileJson(fileId, fallback) {
  try {
    const text = await fetchFileText(fileId);
    return JSON.parse(text);
  } catch (err) {
    console.error("Couldn't parse JSON from Drive file, using fallback", err);
    return fallback;
  }
}

// Uploads NEW file content + metadata in one request (multipart/related).
async function uploadNewFile(parentId, name, contentBlobOrFile, mimeType) {
  const metadata = { name, parents: [parentId] };
  const boundary = "-------314159265358979323846";
  const delimiter = `\r\n--${boundary}\r\n`;
  const closeDelim = `\r\n--${boundary}--`;

  const body = new Blob([
    delimiter,
    "Content-Type: application/json; charset=UTF-8\r\n\r\n",
    JSON.stringify(metadata),
    delimiter,
    `Content-Type: ${mimeType}\r\n\r\n`,
    contentBlobOrFile,
    closeDelim,
  ]);

  const resp = await fetch(`${DRIVE_UPLOAD_URL}?uploadType=multipart&fields=id,name`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${accessToken}`,
      "Content-Type": `multipart/related; boundary="${boundary}"`,
    },
    body,
  });
  if (!resp.ok) throw new Error(`Upload failed (${resp.status})`);
  return resp.json();
}

// Overwrites the CONTENT of an existing file (metadata/name unchanged).
async function updateFileContent(fileId, contentBlobOrString, mimeType) {
  const resp = await fetch(`${DRIVE_UPLOAD_URL}/${fileId}?uploadType=media`, {
    method: "PATCH",
    headers: {
      Authorization: `Bearer ${accessToken}`,
      "Content-Type": mimeType,
    },
    body: contentBlobOrString,
  });
  if (!resp.ok) throw new Error(`Couldn't save file (${resp.status})`);
  return resp.json();
}

// Reads a small JSON "settings" file at the app root, creating it with
// `defaultValue` if it doesn't exist yet. Returns { fileId, data }.
async function loadOrCreateJsonFile(parentId, name, defaultValue) {
  const existing = await findChildByName(parentId, name);
  if (existing) {
    const data = await fetchFileJson(existing.id, defaultValue);
    return { fileId: existing.id, data };
  }
  const created = await uploadNewFile(
    parentId, name, new Blob([JSON.stringify(defaultValue)]), "application/json"
  );
  return { fileId: created.id, data: defaultValue };
}

async function saveJsonFile(fileId, data) {
  await updateFileContent(fileId, JSON.stringify(data, null, 2), "application/json");
}

async function deleteFile(fileId) {
  await gapi.client.drive.files.delete({ fileId });
}

function triggerBrowserDownload(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10000);
}
