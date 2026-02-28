import { useState, useEffect, useRef } from 'react';
import './AppSettings.css';

export default function AppSettings({ onClose, apiBase }) {
  const [tab, setTab]           = useState('company');
  const [form, setForm]         = useState(null);
  const [loading, setLoading]   = useState(true);
  const [saving, setSaving]     = useState(false);
  const [msg, setMsg]           = useState({ text: '', ok: true });
  const [logoPreview, setLogoPreview]   = useState(null);
  const [logoUploading, setLogoUploading] = useState(false);
  const logoRef = useRef(null);

  useEffect(() => {
    fetch(`${apiBase}/settings`)
      .then(r => r.json())
      .then(data => {
        setForm(data);
        if (data.logo_url) setLogoPreview(`${apiBase}${data.logo_url}?t=${Date.now()}`);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [apiBase]);

  const set = (field, value) => setForm(f => ({ ...f, [field]: value }));

  const flash = (text, ok = true) => {
    setMsg({ text, ok });
    setTimeout(() => setMsg({ text: '', ok: true }), 3000);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const res = await fetch(`${apiBase}/settings`, {
        method:  'PUT',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify(form),
      });
      if (!res.ok) throw new Error((await res.json()).detail || 'Save failed');
      flash('Settings saved.');
    } catch (e) {
      flash(e.message || 'Error saving settings.', false);
    } finally {
      setSaving(false);
    }
  };

  const handleLogoUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setLogoUploading(true);
    const fd = new FormData();
    fd.append('file', file);
    try {
      const res = await fetch(`${apiBase}/settings/logo`, { method: 'POST', body: fd });
      if (!res.ok) throw new Error((await res.json()).detail || 'Upload failed');
      setLogoPreview(URL.createObjectURL(file));
      flash('Logo uploaded.');
    } catch (e) {
      flash(e.message || 'Logo upload failed.', false);
    } finally {
      setLogoUploading(false);
      e.target.value = '';
    }
  };

  const TABS = [
    { id: 'company', label: 'Company',  icon: 'M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z' },
    { id: 'pricing', label: 'Pricing',  icon: 'M12 2v20M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6' },
    { id: 'footer',  label: 'Footer',   icon: 'M4 6h16M4 10h16M4 14h10' },
  ];

  return (
    <div className="as-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="as-modal">

        {/* ── Header ── */}
        <div className="as-header">
          <div className="as-header-left">
            <span className="as-header-icon">⚙️</span>
            <div>
              <div className="as-title">App Settings</div>
              <div className="as-subtitle">Company info, pricing rates &amp; quote footer</div>
            </div>
          </div>
          <button className="as-close" onClick={onClose}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>

        {/* ── Tabs ── */}
        <div className="as-tabs">
          {TABS.map(t => (
            <button key={t.id} className={`as-tab${tab === t.id ? ' active' : ''}`} onClick={() => setTab(t.id)}>
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d={t.icon}/>
              </svg>
              {t.label}
            </button>
          ))}
        </div>

        {/* ── Body ── */}
        <div className="as-body">
          {loading ? (
            <div className="as-loading"><span className="as-spinner" />Loading…</div>
          ) : (
            <>
              {/* Company tab */}
              {tab === 'company' && (
                <div className="as-section">
                  <div className="as-grid-2">
                    <div className="as-field as-col-2">
                      <label>Company Name</label>
                      <input value={form?.company_name ?? ''} onChange={e => set('company_name', e.target.value)} placeholder="Acme Fabrications Pvt. Ltd." />
                    </div>
                    <div className="as-field as-col-2">
                      <label>Address</label>
                      <textarea rows={2} value={form?.address ?? ''} onChange={e => set('address', e.target.value)} placeholder="Plot 12, MIDC Industrial Area, Pune – 411019" />
                    </div>
                    <div className="as-field">
                      <label>GST Number</label>
                      <input value={form?.gst_number ?? ''} onChange={e => set('gst_number', e.target.value)} placeholder="27AAAAA0000A1Z5" />
                    </div>
                    <div className="as-field">
                      <label>Logo</label>
                      <div className="as-logo-row">
                        <div className="as-logo-box">
                          {logoPreview
                            ? <img src={logoPreview} alt="logo" className="as-logo-img" />
                            : <span className="as-logo-empty">No logo</span>}
                        </div>
                        <button
                          className="as-btn-outline"
                          onClick={() => logoRef.current?.click()}
                          disabled={logoUploading}
                        >
                          {logoUploading
                            ? <><span className="as-spinner-sm" />Uploading…</>
                            : <>
                                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                  <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M17 8l-5-5-5 5M12 3v12"/>
                                </svg>
                                Upload
                              </>}
                        </button>
                        <span className="as-hint">PNG · JPG · SVG</span>
                        <input ref={logoRef} type="file" accept="image/*" style={{ display: 'none' }} onChange={handleLogoUpload} />
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Pricing tab */}
              {tab === 'pricing' && (
                <div className="as-section">
                  <div className="as-grid-2">
                    <div className="as-field">
                      <label>Price per KG <em>₹/kg</em></label>
                      <input type="number" min="0" step="0.01"
                        value={form?.price_per_kg ?? 0}
                        onChange={e => set('price_per_kg', parseFloat(e.target.value) || 0)} />
                    </div>
                    <div className="as-field">
                      <label>Price per Hour <em>₹/hr</em></label>
                      <input type="number" min="0" step="0.01"
                        value={form?.price_per_hour ?? 0}
                        onChange={e => set('price_per_hour', parseFloat(e.target.value) || 0)} />
                    </div>
                    <div className="as-field">
                      <label>Cutting Cost per Metre <em>₹/m</em></label>
                      <input type="number" min="0" step="0.01"
                        value={form?.cutting_cost_per_meter ?? 0}
                        onChange={e => set('cutting_cost_per_meter', parseFloat(e.target.value) || 0)} />
                    </div>
                    <div className="as-field">
                      <label>Minimum Charge <em>₹</em></label>
                      <input type="number" min="0" step="0.01"
                        value={form?.minimum_charge ?? 0}
                        onChange={e => set('minimum_charge', parseFloat(e.target.value) || 0)} />
                    </div>
                    <div className="as-field">
                      <label>Tax / GST <em>%</em></label>
                      <input type="number" min="0" max="100" step="0.5"
                        value={form?.tax_percent ?? 18}
                        onChange={e => set('tax_percent', parseFloat(e.target.value) || 0)} />
                    </div>

                    {/* Live preview card */}
                    <div className="as-field">
                      <label>Calculation Preview</label>
                      <div className="as-calc-card">
                        <div className="as-calc-row">
                          <span>1 m cut</span>
                          <span>₹{Number(form?.cutting_cost_per_meter || 0).toFixed(2)}</span>
                        </div>
                        <div className="as-calc-row">
                          <span>Min floor</span>
                          <span>₹{Number(form?.minimum_charge || 0).toFixed(2)}</span>
                        </div>
                        <div className="as-calc-row as-calc-tax">
                          <span>+ Tax</span>
                          <span>{form?.tax_percent ?? 0}%</span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Footer tab */}
              {tab === 'footer' && (
                <div className="as-section">
                  <div className="as-field">
                    <label>Quote Footer / Terms &amp; Conditions</label>
                    <textarea
                      rows={10}
                      value={form?.footer_text ?? ''}
                      onChange={e => set('footer_text', e.target.value)}
                      placeholder={
                        '1. Payment due within 30 days of invoice.\n' +
                        '2. Prices valid for 15 days from quote date.\n' +
                        '3. Goods once sold will not be taken back.\n\n' +
                        'Bank: State Bank of India\n' +
                        'A/C No: 00000000000\n' +
                        'IFSC: SBIN0000000'
                      }
                    />
                    <span className="as-hint">Include bank details, payment terms, validity — anything you want printed at the bottom of every quote.</span>
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {/* ── Footer bar ── */}
        <div className="as-footer">
          {msg.text && (
            <span className={`as-msg ${msg.ok ? 'as-msg--ok' : 'as-msg--err'}`}>
              {msg.ok
                ? <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="20 6 9 17 4 12"/></svg>
                : <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>}
              {msg.text}
            </span>
          )}
          <div className="as-footer-btns">
            <button className="as-btn-cancel" onClick={onClose}>Cancel</button>
            <button className="as-btn-save" onClick={handleSave} disabled={saving || loading}>
              {saving
                ? <><span className="as-spinner-sm" />Saving…</>
                : <>
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M19 21H5a2 2 0 01-2-2V5a2 2 0 012-2h11l5 5v11a2 2 0 01-2 2z"/>
                      <polyline points="17 21 17 13 7 13 7 21"/>
                      <polyline points="7 3 7 8 15 8"/>
                    </svg>
                    Save Settings
                  </>}
            </button>
          </div>
        </div>

      </div>
    </div>
  );
}
