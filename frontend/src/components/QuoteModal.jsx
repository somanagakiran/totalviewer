import { useState, useEffect } from 'react';
import './QuoteModal.css';

const MM_TO_M = 0.001;

function fmt(n, dec = 2) {
  return Number(n || 0).toLocaleString('en-IN', { minimumFractionDigits: dec, maximumFractionDigits: dec });
}

function calcPartCost(row, settings) {
  const cpm        = settings.cutting_cost_per_meter || 0;
  const minCharge  = settings.minimum_charge || 0;
  // ep is in mm from the backend; convert to metres for cost calc
  const totalPerim = ((row.ep || 0) + (row.ip || 0)) * MM_TO_M;
  const raw        = totalPerim * cpm;
  return Math.max(raw, minCharge);
}

export default function QuoteModal({ onClose, rows, apiBase }) {
  const [settings, setSettings]     = useState(null);
  const [loading, setLoading]       = useState(true);
  const [logoUrl, setLogoUrl]       = useState(null);
  const [ref, setRef]               = useState(`QT-${Date.now().toString(36).toUpperCase()}`);
  const [quoteDate, setQuoteDate]   = useState(new Date().toISOString().split('T')[0]);
  const [customer, setCustomer]     = useState({ name: '', company: '', gst: '', address: '' });
  const [notes, setNotes]           = useState('');
  useEffect(() => {
    fetch(`${apiBase}/settings`)
      .then(r => r.json())
      .then(data => {
        setSettings(data);
        if (data.logo_url) {
          setLogoUrl(`${apiBase}${data.logo_url}?t=${Date.now()}`);
        }
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [apiBase]);

  const handlePrint = () => {
    window.print();
  };

  if (loading) {
    return (
      <div className="qm-overlay">
        <div className="qm-modal">
          <div className="qm-loading">
            <span className="qm-spinner" />
            Loading settings...
          </div>
        </div>
      </div>
    );
  }

  const s = settings || {};

  // Build line items from DXF rows only (skip images/PDFs with no perimeter)
  const lineItems = rows
    .filter(r => r.ep > 0 || r.ip > 0)
    .map(r => {
      const unitCost  = calcPartCost(r, s);
      const total     = unitCost * (r.qty || 1);
      const perimM    = ((r.ep || 0) + (r.ip || 0)) * MM_TO_M;
      return { ...r, unitCost, total, perimM };
    });

  // Also include rows without perimeter (images/PDFs) as zero-cost line items
  const noPerimItems = rows
    .filter(r => !(r.ep > 0) && !(r.ip > 0))
    .map(r => ({ ...r, unitCost: 0, total: 0, perimM: 0 }));

  const allItems   = [...lineItems, ...noPerimItems];
  const subtotal   = allItems.reduce((acc, r) => acc + r.total, 0);
  const taxAmt     = subtotal * (s.tax_percent || 0) / 100;
  const grandTotal = subtotal + taxAmt;

  return (
    <div className="qm-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="qm-modal">

        {/* Toolbar */}
        <div className="qm-toolbar">
          <div className="qm-toolbar-title">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
              <polyline points="14 2 14 8 20 8"/>
              <line x1="16" y1="13" x2="8" y2="13"/>
              <line x1="16" y1="17" x2="8" y2="17"/>
              <polyline points="10 9 9 9 8 9"/>
            </svg>
            Quotation Preview
          </div>
          <div className="qm-toolbar-actions">
            <button className="qm-btn-print" onClick={handlePrint} title="Print / Save as PDF">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polyline points="6 9 6 2 18 2 18 9"/>
                <path d="M6 18H4a2 2 0 01-2-2v-5a2 2 0 012-2h16a2 2 0 012 2v5a2 2 0 01-2 2h-2"/>
                <rect x="6" y="14" width="12" height="8"/>
              </svg>
              Print / PDF
            </button>
            <button className="qm-btn-close" onClick={onClose} title="Close">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="18" y1="6" x2="6" y2="18"/>
                <line x1="6" y1="6" x2="18" y2="18"/>
              </svg>
            </button>
          </div>
        </div>

        <div className="qm-layout">

          {/* ── Reference sidebar (editable) ── */}
          <div className="qm-sidebar">
            <div className="qm-sidebar-title">Reference Details</div>

            <div className="qm-ref-field">
              <label>Quote Reference</label>
              <input value={ref} onChange={e => setRef(e.target.value)} />
            </div>
            <div className="qm-ref-field">
              <label>Date</label>
              <input type="date" value={quoteDate} onChange={e => setQuoteDate(e.target.value)} />
            </div>

            <div className="qm-sidebar-sep" />
            <div className="qm-sidebar-title">Customer Info</div>

            <div className="qm-ref-field">
              <label>Customer Name</label>
              <input value={customer.name} onChange={e => setCustomer(p => ({ ...p, name: e.target.value }))} placeholder="John Smith" />
            </div>
            <div className="qm-ref-field">
              <label>Company</label>
              <input value={customer.company} onChange={e => setCustomer(p => ({ ...p, company: e.target.value }))} placeholder="ABC Industries" />
            </div>
            <div className="qm-ref-field">
              <label>GST</label>
              <input value={customer.gst} onChange={e => setCustomer(p => ({ ...p, gst: e.target.value }))} placeholder="GST Number" />
            </div>
            <div className="qm-ref-field">
              <label>Address</label>
              <textarea rows={3} value={customer.address} onChange={e => setCustomer(p => ({ ...p, address: e.target.value }))} placeholder="Customer address" />
            </div>

            <div className="qm-sidebar-sep" />
            <div className="qm-sidebar-title">Additional Notes</div>
            <div className="qm-ref-field">
              <textarea rows={4} value={notes} onChange={e => setNotes(e.target.value)} placeholder="Delivery: 7–10 working days&#10;Validity: 15 days" />
            </div>
          </div>

          {/* ── Quote document ── */}
          <div className="qm-doc">

            {/* Company header */}
            <div className="qm-doc-header">
              <div className="qm-company-info">
                {logoUrl && (
                  <img src={logoUrl} alt="Company logo" className="qm-logo" />
                )}
                <div className="qm-company-text">
                  <div className="qm-company-name">{s.company_name || 'Your Company'}</div>
                  {s.address && <div className="qm-company-detail">{s.address}</div>}
                  {s.gst_number && <div className="qm-company-detail">GST: {s.gst_number}</div>}
                  {s.contact_info && <div className="qm-company-detail">{s.contact_info}</div>}
                </div>
              </div>
              <div className="qm-doc-meta">
                <div className="qm-doc-title">QUOTATION</div>
                <div className="qm-doc-ref-box">
                  <div className="qm-meta-row"><span>Ref No.</span><span>{ref}</span></div>
                  <div className="qm-meta-row"><span>Date</span><span>{new Date(quoteDate).toLocaleDateString('en-IN', { day:'2-digit', month:'short', year:'numeric' })}</span></div>
                </div>
              </div>
            </div>

            {/* Bill to */}
            {(customer.name || customer.company) && (
              <div className="qm-bill-to">
                <div className="qm-section-label">Bill To</div>
                {customer.name    && <div className="qm-bt-name">{customer.name}</div>}
                {customer.company && <div className="qm-bt-detail">{customer.company}</div>}
                {customer.gst     && <div className="qm-bt-detail">GST: {customer.gst}</div>}
                {customer.address && <div className="qm-bt-detail">{customer.address}</div>}
              </div>
            )}

            {/* Line items table */}
            <table className="qm-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Part / Description</th>
                  <th>Material</th>
                  <th className="num">Cut Length (m)</th>
                  <th className="num">Holes</th>
                  <th className="num">Qty</th>
                  <th className="num">Unit Cost (₹)</th>
                  <th className="num">Amount (₹)</th>
                </tr>
              </thead>
              <tbody>
                {allItems.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="qm-no-parts">No parts loaded. Upload a DXF file first.</td>
                  </tr>
                ) : (
                  allItems.map((item, i) => (
                    <tr key={item.id}>
                      <td className="num">{i + 1}</td>
                      <td>
                        <div className="qm-part-name">{item.partName || item.fileName}</div>
                        <div className="qm-part-sub">{item.fileName}</div>
                      </td>
                      <td>{item.material || '—'}</td>
                      <td className="num">{item.perimM > 0 ? fmt(item.perimM, 3) : '—'}</td>
                      <td className="num">{item.holes || 0}</td>
                      <td className="num">{item.qty || 1}</td>
                      <td className="num">{item.unitCost > 0 ? `₹${fmt(item.unitCost)}` : '—'}</td>
                      <td className="num">{item.total > 0 ? `₹${fmt(item.total)}` : '—'}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>

            {/* Cost summary */}
            <div className="qm-summary">
              <div className="qm-summary-row">
                <span>Subtotal</span>
                <span>₹{fmt(subtotal)}</span>
              </div>
              <div className="qm-summary-row">
                <span>GST ({s.tax_percent || 0}%)</span>
                <span>₹{fmt(taxAmt)}</span>
              </div>
              <div className="qm-summary-row qm-summary-total">
                <span>Total Payable</span>
                <span>₹{fmt(grandTotal)}</span>
              </div>
            </div>

            {/* Notes */}
            {notes && (
              <div className="qm-notes-block">
                <div className="qm-section-label">Notes</div>
                <div className="qm-notes-text">{notes}</div>
              </div>
            )}

            {/* Footer strip */}
            <div className="qm-doc-footer">
              <div className="qm-footer-left">
                {s.footer_text && (
                  <div className="qm-terms">
                    <div className="qm-section-label">Terms, Conditions &amp; Bank Details</div>
                    <div className="qm-terms-text">{s.footer_text}</div>
                  </div>
                )}
              </div>
              <div className="qm-footer-right">
                <div className="qm-sig-area">
                  <div className="qm-sig-line" />
                  <div className="qm-sig-name">{s.company_name || 'Your Company'}</div>
                  <div className="qm-sig-label">Authorised Signatory</div>
                </div>
              </div>
            </div>

          </div>{/* /.qm-doc */}
        </div>{/* /.qm-layout */}
      </div>
    </div>
  );
}
