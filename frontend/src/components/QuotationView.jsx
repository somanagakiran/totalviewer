import { useState, useEffect } from 'react';
import './QuotationView.css';

// ── Helpers ────────────────────────────────────────────────────

const DENSITY = { MS: 7.85, SS: 8.0, AL: 2.70 };

function density(material) {
  return DENSITY[String(material).toUpperCase()] ?? 7.85;
}

/** Weight in kg: area (mm²) × thickness (mm) × density (g/cm³) → kg */
function weightKg(area_mm2, thickness_mm, mat) {
  // 1 mm² × 1 mm = 1 mm³;  1 g/cm³ = 0.000001 kg/mm³
  return (area_mm2 * thickness_mm * density(mat)) / 1_000_000;
}

function fmt(n, dec = 2) {
  return Number(n || 0).toLocaleString('en-IN', {
    minimumFractionDigits: dec,
    maximumFractionDigits: dec,
  });
}

function fmtDate(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  return isNaN(d) ? iso : d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
}

function genRef() {
  const now   = new Date();
  const yy    = String(now.getFullYear()).slice(2);
  const mm    = String(now.getMonth() + 1).padStart(2, '0');
  const rand  = Math.floor(Math.random() * 900 + 100);
  return `QT-${yy}${mm}-${rand}`;
}

// ── Main component ─────────────────────────────────────────────

export default function QuotationView({ rows, apiBase, stock, onBack }) {
  const [settings, setSettings] = useState(null);
  const [loading, setLoading]   = useState(true);
  const [logoUrl, setLogoUrl]   = useState(null);

  // Editable quote fields (sidebar)
  const [qRef,   setQRef]   = useState(genRef);
  const [qDate,  setQDate]  = useState(new Date().toISOString().split('T')[0]);
  const [thick,  setThick]  = useState(String(stock?.thickness ?? 3));
  const [cust,   setCust]   = useState({ name: '', company: '', gst: '', address: '' });
  const [delivery, setDelivery] = useState('');
  const [validity, setValidity] = useState('15 days from quote date');
  const [notes, setNotes]   = useState('');

  useEffect(() => {
    fetch(`${apiBase}/settings`)
      .then(r => r.json())
      .then(data => {
        setSettings(data);
        if (data.logo_url) setLogoUrl(`${apiBase}${data.logo_url}?t=${Date.now()}`);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [apiBase]);

  const s  = settings || {};
  const t  = parseFloat(thick) || 0;   // thickness in mm

  // ── Build line items ─────────────────────────────────────────
  const items = rows
    .filter(r => r.fileType === 'dxf')
    .map((r, i) => {
      const area_mm2    = r.analysisResult?.outer_boundary_area ?? 0;
      const wt          = weightKg(area_mm2, t, r.material);
      const wt_total    = wt * (r.qty || 1);
      const cut_m       = ((r.ep || 0) + (r.ip || 0)) * 0.001;
      const mat_cost    = wt * (s.price_per_kg || 0);
      const cut_cost    = cut_m * (s.cutting_cost_per_meter || 0);
      const unit_rate   = Math.max(mat_cost + cut_cost, s.minimum_charge || 0);
      const amount      = unit_rate * (r.qty || 1);
      return {
        no:        i + 1,
        name:      r.partName || `Part ${i + 1}`,
        file:      r.fileName,
        material:  r.material || 'MS',
        area_cm2:  area_mm2 / 100,
        wt,
        wt_total,
        cut_m,
        qty:       r.qty || 1,
        unit_rate,
        amount,
      };
    });

  const subtotal   = items.reduce((s, r) => s + r.amount, 0);
  const taxAmt     = subtotal * (s.tax_percent || 0) / 100;
  const grandTotal = subtotal + taxAmt;
  const totalWt    = items.reduce((s, r) => s + r.wt_total, 0);

  if (loading) {
    return (
      <div className="qv-loading-screen">
        <span className="qv-spinner" />
        <span>Preparing quotation…</span>
      </div>
    );
  }

  return (
    <div className="qv-root">

      {/* ── Control bar (screen only, not printed) ── */}
      <div className="qv-controlbar no-print">
        <button className="qv-btn-back" onClick={onBack}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="19" y1="12" x2="5" y2="12"/>
            <polyline points="12 19 5 12 12 5"/>
          </svg>
          Back to Workspace
        </button>

        <div className="qv-controlbar-center">
          <span className="qv-doc-badge">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
              <polyline points="14 2 14 8 20 8"/>
            </svg>
            Quotation — {qRef}
          </span>
        </div>

        <button className="qv-btn-print" onClick={() => setTimeout(() => window.print(), 500)}>
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="6 9 6 2 18 2 18 9"/>
            <path d="M6 18H4a2 2 0 01-2-2v-5a2 2 0 012-2h16a2 2 0 012 2v5a2 2 0 01-2 2h-2"/>
            <rect x="6" y="14" width="12" height="8"/>
          </svg>
          Print / Save PDF
        </button>
      </div>

      {/* ── Main workspace ── */}
      <div className="qv-workspace">

        {/* ── Sidebar: editable fields (screen only, not printed) ── */}
        <aside className="qv-sidebar no-print">

          <div className="qv-sb-group">
            <div className="qv-sb-title">Quote Details</div>
            <div className="qv-sb-field">
              <label>Reference No.</label>
              <input value={qRef} onChange={e => setQRef(e.target.value)} />
            </div>
            <div className="qv-sb-field">
              <label>Date</label>
              <input type="date" value={qDate} onChange={e => setQDate(e.target.value)} />
            </div>
            <div className="qv-sb-field">
              <label>Validity</label>
              <input value={validity} onChange={e => setValidity(e.target.value)} placeholder="15 days from quote date" />
            </div>
          </div>

          <div className="qv-sb-group">
            <div className="qv-sb-title">Customer</div>
            <div className="qv-sb-field">
              <label>Name</label>
              <input value={cust.name} onChange={e => setCust(p => ({ ...p, name: e.target.value }))} placeholder="Customer name" />
            </div>
            <div className="qv-sb-field">
              <label>Company</label>
              <input value={cust.company} onChange={e => setCust(p => ({ ...p, company: e.target.value }))} placeholder="Company name" />
            </div>
            <div className="qv-sb-field">
              <label>GST No.</label>
              <input value={cust.gst} onChange={e => setCust(p => ({ ...p, gst: e.target.value }))} placeholder="GST Number" />
            </div>
            <div className="qv-sb-field">
              <label>Address</label>
              <textarea rows={3} value={cust.address} onChange={e => setCust(p => ({ ...p, address: e.target.value }))} placeholder="Customer address" />
            </div>
          </div>

          <div className="qv-sb-group">
            <div className="qv-sb-title">Material Options</div>
            <div className="qv-sb-field">
              <label>Sheet Thickness (mm)</label>
              <input type="number" min="0.1" step="0.1" value={thick}
                onChange={e => setThick(e.target.value)} />
            </div>
            <div className="qv-sb-field">
              <label>Delivery Terms</label>
              <input value={delivery} onChange={e => setDelivery(e.target.value)} placeholder="Ex-works / Door delivery" />
            </div>
          </div>

          <div className="qv-sb-group">
            <div className="qv-sb-title">Remarks</div>
            <div className="qv-sb-field">
              <textarea rows={4} value={notes} onChange={e => setNotes(e.target.value)}
                placeholder="Any additional remarks for this quotation…" />
            </div>
          </div>

          {/* Live summary in sidebar */}
          <div className="qv-sb-summary">
            <div className="qv-sb-summary-row">
              <span>Parts</span><span>{items.length}</span>
            </div>
            <div className="qv-sb-summary-row">
              <span>Total Wt</span><span>{fmt(totalWt, 3)} kg</span>
            </div>
            <div className="qv-sb-summary-row">
              <span>Subtotal</span><span>₹{fmt(subtotal)}</span>
            </div>
            <div className="qv-sb-summary-row qv-sb-total">
              <span>Grand Total</span><span>₹{fmt(grandTotal)}</span>
            </div>
          </div>

        </aside>

        {/* ── A4 Document ── */}
        <div className="qv-page-area">
          <div className="qv-a4" id="quotation-container">

            {/* ── Document header ── */}
            <div className="qv-hdr">
              <div className="qv-hdr-company">
                {logoUrl && <img src={logoUrl} className="qv-logo" alt="logo" />}
                <div className="qv-hdr-text">
                  <div className="qv-company-name">{s.company_name || 'Your Company'}</div>
                  {s.address     && <div className="qv-company-line">{s.address}</div>}
                  {s.gst_number  && <div className="qv-company-line">GSTIN: {s.gst_number}</div>}
                </div>
              </div>
              <div className="qv-hdr-meta">
                <div className="qv-doc-title">QUOTATION</div>
                <table className="qv-meta-table">
                  <tbody>
                    <tr><td>Ref. No.</td><td>{qRef}</td></tr>
                    <tr><td>Date</td><td>{fmtDate(qDate)}</td></tr>
                    {validity && <tr><td>Valid till</td><td>{validity}</td></tr>}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="qv-hdr-rule" />

            {/* ── Bill To ── */}
            {(cust.name || cust.company) && (
              <div className="qv-bill-to">
                <div className="qv-label-tag">BILL TO</div>
                {cust.company && <div className="qv-bt-company">{cust.company}</div>}
                {cust.name    && <div className="qv-bt-name">{cust.name}</div>}
                {cust.gst     && <div className="qv-bt-line">GSTIN: {cust.gst}</div>}
                {cust.address && <div className="qv-bt-line">{cust.address}</div>}
                {delivery     && <div className="qv-bt-line">Delivery: {delivery}</div>}
              </div>
            )}

            {/* ── Line items ── */}
            <table className="qv-table">
              <thead>
                <tr>
                  <th className="th-no">#</th>
                  <th className="th-desc">Description</th>
                  <th className="th-mat">Material</th>
                  <th className="th-thk">Thk<br/>(mm)</th>
                  <th className="th-wt">Wt/pc<br/>(kg)</th>
                  <th className="th-cut">Cut Length<br/>(m)</th>
                  <th className="th-qty">Qty</th>
                  <th className="th-rate">Unit Rate<br/>(₹)</th>
                  <th className="th-amt">Amount<br/>(₹)</th>
                </tr>
              </thead>
              <tbody>
                {items.length === 0 ? (
                  <tr>
                    <td colSpan={9} className="qv-no-rows">
                      No DXF parts loaded. Upload a DXF file from the workspace first.
                    </td>
                  </tr>
                ) : (
                  items.map(item => (
                    <tr key={item.no}>
                      <td className="td-no">{item.no}</td>
                      <td className="td-desc">
                        <div className="qv-part-name">{item.name}</div>
                        <div className="qv-part-sub">
                          {fmt(item.area_cm2, 2)} cm² gross area
                          {item.cut_m > 0 && <> &nbsp;·&nbsp; {fmt(item.cut_m, 3)} m cut path</>}
                        </div>
                      </td>
                      <td className="td-mat">{item.material}</td>
                      <td className="td-num">{t > 0 ? fmt(t, 1) : '—'}</td>
                      <td className="td-num">{t > 0 ? fmt(item.wt, 3) : '—'}</td>
                      <td className="td-num">{item.cut_m > 0 ? fmt(item.cut_m, 3) : '—'}</td>
                      <td className="td-num">{item.qty}</td>
                      <td className="td-num">{item.unit_rate > 0 ? fmt(item.unit_rate) : '—'}</td>
                      <td className="td-amt">{item.amount > 0 ? fmt(item.amount) : '—'}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>

            {/* ── Totals ── */}
            <div className="qv-totals-row">
              <div className="qv-totals-left">
                {t > 0 && items.length > 0 && (
                  <div className="qv-weight-summary">
                    <span className="qv-label-tag">WEIGHT SUMMARY</span>
                    <table className="qv-wt-table">
                      <tbody>
                        {items.map(item => (
                          <tr key={item.no}>
                            <td>{item.name}</td>
                            <td>{fmt(item.wt, 3)} kg × {item.qty} =</td>
                            <td className="wt-total">{fmt(item.wt_total, 3)} kg</td>
                          </tr>
                        ))}
                        <tr className="wt-grand">
                          <td colSpan={2}>Total Weight</td>
                          <td className="wt-total">{fmt(totalWt, 3)} kg</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                )}
              </div>

              <div className="qv-totals-box">
                <div className="qv-total-row">
                  <span>Subtotal</span>
                  <span>₹ {fmt(subtotal)}</span>
                </div>
                {s.tax_percent > 0 && (
                  <div className="qv-total-row">
                    <span>GST / Tax ({s.tax_percent}%)</span>
                    <span>₹ {fmt(taxAmt)}</span>
                  </div>
                )}
                <div className="qv-total-row qv-grand-total">
                  <span>TOTAL PAYABLE</span>
                  <span>₹ {fmt(grandTotal)}</span>
                </div>
              </div>
            </div>

            {/* ── Notes ── */}
            {notes && (
              <div className="qv-notes">
                <div className="qv-label-tag">REMARKS</div>
                <div className="qv-notes-text">{notes}</div>
              </div>
            )}

            {/* ── Footer ── */}
            <div className="qv-footer">
              <div className="qv-footer-terms">
                {s.footer_text ? (
                  <>
                    <div className="qv-label-tag">TERMS &amp; CONDITIONS</div>
                    <div className="qv-terms-text">{s.footer_text}</div>
                  </>
                ) : (
                  <div className="qv-terms-placeholder">
                    Add terms &amp; conditions in Settings → Footer tab.
                  </div>
                )}
              </div>
              <div className="qv-footer-sig">
                <div className="qv-sig-box">
                  <div className="qv-sig-area-blank" />
                  <div className="qv-sig-company">{s.company_name || 'Your Company'}</div>
                  <div className="qv-sig-label">Authorised Signatory</div>
                </div>
              </div>
            </div>

            <div className="qv-doc-watermark no-print-hide">
              Generated by Total Viewer
            </div>

          </div>{/* /.qv-a4 */}
        </div>{/* /.qv-page-area */}

      </div>{/* /.qv-workspace */}
    </div>/* /.qv-root */
  );
}
