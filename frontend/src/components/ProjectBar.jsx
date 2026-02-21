import { useState } from 'react';
import './ProjectBar.css';

export default function ProjectBar({
  projects,
  selectedProjectId,
  onSelectProject,
  onCreateProject,
  onDeleteProject,
}) {
  const [newName, setNewName] = useState('');

  const handleCreate = () => {
    const trimmed = newName.trim();
    if (!trimmed) return;
    onCreateProject(trimmed);
    setNewName('');
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') handleCreate();
  };

  return (
    <div className="project-bar">
      <span className="pb-label">Project</span>

      <select
        className="pb-select"
        value={selectedProjectId ?? ''}
        onChange={e => onSelectProject(e.target.value ? Number(e.target.value) : null)}
      >
        <option value="">— none —</option>
        {projects.map(p => (
          <option key={p.id} value={p.id}>{p.name}</option>
        ))}
      </select>

      {selectedProjectId && (
        <button
          className="pb-btn pb-btn--delete"
          title="Delete selected project and all its parts"
          onClick={() => onDeleteProject(selectedProjectId)}
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <polyline points="3 6 5 6 21 6"/>
            <path d="M19 6l-1 14H6L5 6"/>
            <path d="M10 11v6M14 11v6"/>
            <path d="M9 6V4h6v2"/>
          </svg>
          <span>Delete</span>
        </button>
      )}

      <div className="pb-divider" />

      <input
        className="pb-input"
        placeholder="New project name…"
        value={newName}
        onChange={e => setNewName(e.target.value)}
        onKeyDown={handleKeyDown}
        maxLength={80}
      />
      <button
        className="pb-btn pb-btn--create"
        onClick={handleCreate}
        disabled={!newName.trim()}
        title="Create new project"
      >
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
          <line x1="12" y1="5" x2="12" y2="19"/>
          <line x1="5" y1="12" x2="19" y2="12"/>
        </svg>
        <span>Create</span>
      </button>
    </div>
  );
}
