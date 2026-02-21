// All backend REST calls go through this module.
// Components never fetch directly — they call these helpers.

const base = () => import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

// ── Projects ─────────────────────────────────────────────────

export async function fetchProjects() {
  const res = await fetch(`${base()}/projects`);
  if (!res.ok) throw new Error(`GET /projects → ${res.status}`);
  return res.json();
}

export async function createProject(name) {
  const res = await fetch(`${base()}/projects`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({ name }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `POST /projects → ${res.status}`);
  }
  return res.json();
}

export async function deleteProject(id) {
  const res = await fetch(`${base()}/projects/${id}`, { method: 'DELETE' });
  if (!res.ok) throw new Error(`DELETE /projects/${id} → ${res.status}`);
  return res.json();
}

// ── Parts within a project ────────────────────────────────────

export async function fetchProjectParts(projectId) {
  const res = await fetch(`${base()}/projects/${projectId}/parts`);
  if (!res.ok) throw new Error(`GET /projects/${projectId}/parts → ${res.status}`);
  return res.json();
}

export async function uploadPartToProject(projectId, file, signal) {
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(`${base()}/projects/${projectId}/parts`, {
    method: 'POST',
    body:   form,
    signal,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Upload to project failed: ${res.status}`);
  }
  return res.json();
}

// ── Part geometry (lazy-load when clicking a DB row) ──────────

export async function fetchPartGeometry(partId) {
  const res = await fetch(`${base()}/parts/${partId}/geometry`);
  if (!res.ok) throw new Error(`GET /parts/${partId}/geometry → ${res.status}`);
  return res.json();
}

// ── Plain upload (no project — session only) ──────────────────

export async function uploadDxf(file, signal) {
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(`${base()}/upload`, {
    method: 'POST',
    body:   form,
    signal,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Upload failed: ${res.status}`);
  }
  return res.json();
}
