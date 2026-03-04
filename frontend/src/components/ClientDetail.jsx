import './ClientDetail.css';

const STATUS_CLASS = {
  'Quoted':           'cd-qs-quoted',
  'Order Received':   'cd-qs-order',
  'Under Production': 'cd-qs-production',
  'Dispatched':       'cd-qs-dispatched',
  'Lost':             'cd-qs-lost',
  'Dropped':          'cd-qs-dropped',
};

function fmt(n) {
  return Number(n || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function fmtDate(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return isNaN(d) ? iso : d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
}

export default function ClientDetail({ client, quotes, onBack }) {
  if (!client) return null;

  const clientQuotes  = quotes.filter(q => q.clientId === client.id);
  const totalRevenue  = clientQuotes.reduce((s, q) => s + (q.amount || 0), 0);
  const totalParts    = clientQuotes.reduce((s, q) => s + (q.parts || 0), 0);
  const totalWeight   = clientQuotes.reduce((s, q) => s + (q.totalWeight || 0), 0);

  return (
    <div className="cd-root">

      {/* ── Header ── */}
      <div className="cd-header">
        <button className="cd-btn-back" onClick={onBack}>
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="19" y1="12" x2="5" y2="12"/>
            <polyline points="12 19 5 12 12 5"/>
          </svg>
          Clients
        </button>
        <div className="cd-header-right">
          <div className="cd-avatar">{client.company.charAt(0).toUpperCase()}</div>
          <div>
            <h1 className="cd-company-name">{client.company}</h1>
            {client.city && <div className="cd-city">{client.city}</div>}
          </div>
        </div>
      </div>

      {/* ── Info cards ── */}
      <div className="cd-info-grid">
        <div className="cd-info-card">
          <div className="cd-ic-label">Address</div>
          <div className="cd-ic-value">{client.address || '—'}</div>
        </div>
        <div className="cd-info-card">
          <div className="cd-ic-label">GST Number</div>
          <div className="cd-ic-value cd-mono">{client.gst || '—'}</div>
        </div>
        <div className="cd-info-card cd-info-card--stat">
          <div className="cd-ic-label">Total Quotes</div>
          <div className="cd-ic-stat">{clientQuotes.length}</div>
        </div>
        <div className="cd-info-card cd-info-card--stat">
          <div className="cd-ic-label">Total Revenue</div>
          <div className="cd-ic-stat cd-ic-stat--green">₹ {fmt(totalRevenue)}</div>
        </div>
        <div className="cd-info-card cd-info-card--stat">
          <div className="cd-ic-label">Total Parts</div>
          <div className="cd-ic-stat">{totalParts}</div>
        </div>
        <div className="cd-info-card cd-info-card--stat">
          <div className="cd-ic-label">Total Weight</div>
          <div className="cd-ic-stat">{totalWeight.toFixed(2)} kg</div>
        </div>
      </div>

      {/* ── Quotes section ── */}
      <div className="cd-quotes-section">
        <div className="cd-section-header">
          <h2 className="cd-section-title">Quotes</h2>
          <span className="cd-quote-count-badge">{clientQuotes.length}</span>
        </div>
        <div className="cd-table-wrap">
          {clientQuotes.length === 0 ? (
            <div className="cd-empty">
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M20.59 13.41l-7.17 7.17a2 2 0 01-2.83 0L2 12V2h10l8.59 8.59a2 2 0 010 2.82z"/>
                <line x1="7" y1="7" x2="7.01" y2="7"/>
              </svg>
              <p>No quotes for this client yet.</p>
            </div>
          ) : (
            <table className="cd-table">
              <thead>
                <tr>
                  <th>Quote No</th>
                  <th>Date</th>
                  <th className="cd-th-right">Amount (₹)</th>
                  <th className="cd-th-center">Parts</th>
                  <th className="cd-th-center">Weight (kg)</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {clientQuotes.map(q => (
                  <tr key={q.id} className="cd-row">
                    <td className="cd-td-mono">{q.quoteNo}</td>
                    <td className="cd-td-date">{fmtDate(q.date)}</td>
                    <td className="cd-td-right cd-td-amount">₹ {fmt(q.amount)}</td>
                    <td className="cd-td-center">{q.parts || '—'}</td>
                    <td className="cd-td-center">{q.totalWeight ? Number(q.totalWeight).toFixed(2) : '—'}</td>
                    <td>
                      <span className={`cd-status-badge ${STATUS_CLASS[q.status] || ''}`}>
                        {q.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

    </div>
  );
}
