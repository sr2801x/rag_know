const BASE = (import.meta.env.VITE_API_URL || "/api").replace(/\/$/, "");

async function handle(res) {
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed (${res.status})`);
  }
  return res.json();
}

export const listDocuments = () => fetch(`${BASE}/documents`).then(handle);

export const uploadPdf = (file) => {
  const form = new FormData();
  form.append("file", file);
  return fetch(`${BASE}/upload`, { method: "POST", body: form }).then(handle);
};

export const deleteDocument = (id) =>
  fetch(`${BASE}/documents/${id}`, { method: "DELETE" }).then(handle);

export const ask = (question) =>
  fetch(`${BASE}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  }).then(handle);
