import { useState } from 'react';
import './ClientsPage.css';

function quoteCountFor(clientId, quotes) {
  return quotes.filter(q => q.clientId === clientId).length;
}

export default function ClientsPage({ clients, quotes, onSelectClient, onAddClient }) {
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ company: '', city: '', address: '', gst: '' });
  const [search, setSearch] = useState('');

  const set = (f, v) => setForm(prev => ({ ...prev, [f]: v }));

  const handleAdd = () => {
    if (!form.company.trim()) { alert('Company name is required'); return; }
    onAddClient(form);
    setForm({ company: '', city: '', address: '', gst: '' });
    setShowForm(false);
  };

  const filtered = clients.filter(c => {
    if (!search) return true;
    const s = search.toLowerCase();
    return c.company.toLowerCase().includes(s) || (c.city || '').toLowerCase().includes(s);
  });

  return (
    <div className="cp-root">

      {/* ── Header ── */}
      <div className="cp-header">
        <div className="cp-title-row">
          <div className="cp-page-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/>
              <circle cx="9" cy="7" r="4"/>
              <path d="M23 21v-2a4 4 0 00-3-3.87"/>
              <path d="M16 3.13a4 4 0 010 7.75"/>
            </svg>
          </div>
          <h1 className="cp-page-title">Clients</h1>
          <span className="cp-count-badge">{clients.length}</span>
        </div>
        <button
          className={`cp-btn-add${showForm ? ' active' : ''}`}
          onClick={() => setShowForm(v => !v)}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
          </svg>
          Add Client
        </button>
      </div>

      {/* ── Inline add form ── */}
      {showForm && (
        <div className="cp-add-form">
          <div className="cp-af-title">New Client</div>
          <div className="cp-af-grid">
            <div className="cp-af-field cp-af-field--wide">
              <label>Company <span className="cp-req">*</span></label>
              <input value={form.company} onChange={e => set('company', e.target.value)} placeholder="Company name" autoFocus />
            </div>
            <div className="cp-af-field">
              <label>City</label>
              <input value={form.city} onChange={e => set('city', e.target.value)} placeholder="City" />
            </div>
            <div className="cp-af-field cp-af-field--wide">
              <label>Address</label>
              <input value={form.address} onChange={e => set('address', e.target.value)} placeholder="Full address" />
            </div>
            <div className="cp-af-field">
              <label>GST Number</label>
              <input value={form.gst} onChange={e => set('gst', e.target.value)} placeholder="GST No." />
            </div>
          </div>
          <div className="cp-af-actions">
            <button className="cp-af-btn cp-af-btn--cancel" onClick={() => setShowForm(false)}>Cancel</button>
            <button className="cp-af-btn cp-af-btn--save" onClick={handleAdd}>
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polyline points="20 6 9 17 4 12"/>
              </svg>
              Save Client
            </button>
          </div>
        </div>
      )}

      {/* ── Search ── */}
      <div className="cp-toolbar">
        <div className="cp-search-wrap">
          <svg className="cp-search-icon" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
          </svg>
          <input
            className="cp-search"
            placeholder="Search by company or city…"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
          {search && (
            <button className="cp-search-clear" onClick={() => setSearch('')}>✕</button>
          )}
        </div>
      </div>

      {/* ── Table ── */}
      <div className="cp-table-wrap">
        {filtered.length === 0 ? (
          <div className="cp-empty-state">
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/>
              <circle cx="9" cy="7" r="4"/>
              <path d="M23 21v-2a4 4 0 00-3-3.87"/>
              <path d="M16 3.13a4 4 0 010 7.75"/>
            </svg>
            <p>{clients.length === 0 ? 'No clients yet. Add a client or save a quote.' : 'No clients match your search.'}</p>
          </div>
        ) : (
          <table className="cp-table">
            <thead>
              <tr>
                <th>Company Name</th>
                <th className="cp-th-center">Quotes</th>
                <th>City</th>
                <th>Address</th>
                <th>GST Number</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(c => (
                <tr key={c.id} className="cp-row" onClick={() => onSelectClient(c.id)} title="View client details">
                  <td className="cp-td-company">
                    <div className="cp-company-avatar">{c.company.charAt(0).toUpperCase()}</div>
                    {c.company}
                  </td>
                  <td className="cp-td-center">
                    <span className="cp-quote-count">{quoteCountFor(c.id, quotes)}</span>
                  </td>
                  <td className="cp-td-city">{c.city || '—'}</td>
                  <td className="cp-td-address">{c.address || '—'}</td>
                  <td className="cp-td-mono">{c.gst || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

    </div>
  );
}
