import { useState, useEffect, useRef } from 'react';
import './AdminPanel.css';

export default function AdminPanel({ onClose, token, apiBase }) {
  const [tab, setTab]             = useState('company');
  const [settings, setSettings]   = useState(null);
  const [loading, setLoading]     = useState(true);
  const [saving, setSaving]       = useState(false);
  const [saveMsg, setSaveMsg]     = useState({ text: '', type: '' });
  const [logoPreview, setLogoPreview] = useState(null);
  const [logoUploading, setLogoUploading] = useState(false);
  const logoInputRef = useRef(null);

  useEffect(() => {
    fetch(`${apiBase}/admin/settings`)
      .then(r => r.json())
      .then(data => {
        setSettings(data);
        if (data.logo_url) {
          setLogoPreview(`${apiBase}${data.logo_url}?t=${Date.now()}`);
        }
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [apiBase]);

  const handleChange = (field, value) => {
    setSettings(prev => ({ ...prev, [field]: value }));
  };

  const showMsg = (text, type = 'ok') => {
    setSaveMsg({ text, type });
    setTimeout(() => setSaveMsg({ text: '', type: '' }), 3500);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const res = await fetch(`${apiBase}/admin/settings`, {
        method:  'PUT',
        headers: {
          'Content-Type':  'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify(settings),
      });
      if (!res.ok) {
        const d = await res.json();
        throw new Error(d.detail || 'Save failed');
      }
      showMsg('Settings saved successfully.', 'ok');
    } catch (err) {
      showMsg(err.message || 'Error saving settings.', 'error');
    } finally {
      setSaving(false);
    }
  };

  const handleLogoUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setLogoUploading(true);
    const formData = new FormData();
    formData.append('file', file);
    try {
      const res = await fetch(`${apiBase}/admin/logo`, {
        method:  'POST',
        headers: { 'Authorization': `Bearer ${token}` },
        body:    formData,
      });
      if (!res.ok) {
        const d = await res.json();
        throw new Error(d.detail || 'Upload failed');
      }
      setLogoPreview(URL.createObjectURL(file));
      showMsg('Logo uploaded.', 'ok');
    } catch (err) {
      showMsg(err.message || 'Logo upload failed.', 'error');
    } finally {
      setLogoUploading(false);
      e.target.value = '';
    }
  };

  const TABS = [
    { id: 'company', label: 'Company Details',  icon: 'M19 21H5a2 2 0 01-2-2V5a2 2 0 012-2h11l5 5v11a2 2 0 01-2 2z' },
    { id: 'costs',   label: 'Cost Settings',    icon: 'M12 2v20M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6' },
    { id: 'footer',  label: 'Quotation Footer', icon: 'M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z' },
  ];

  return (
    <div className="ap-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="ap-modal">

        {/* Header */}
        <div className="ap-header">
          <div className="ap-header-left">
            <div className="ap-header-icon">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="8" r="4"/>
                <path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/>
              </svg>
            </div>
            <div>
              <div className="ap-title">Admin Panel</div>
              <div className="ap-subtitle">Manage company info, pricing & quote settings</div>
            </div>
          </div>
          <button className="ap-close" onClick={onClose} title="Close">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18"/>
              <line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>

        {/* Tabs */}
        <div className="ap-tabs">
          {TABS.map(t => (
            <button
              key={t.id}
              className={`ap-tab${tab === t.id ? ' active' : ''}`}
              onClick={() => setTab(t.id)}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d={t.icon}/>
              </svg>
              {t.label}
            </button>
          ))}
        </div>

        {/* Body */}
        <div className="ap-body">
          {loading ? (
            <div className="ap-loading">
              <span className="ap-spinner" />
              Loading settings...
            </div>
          ) : (
            <>
              {/* ── Company Details ── */}
              {tab === 'company' && (
                <div className="ap-section">
                  <div className="ap-section-title">Company Information</div>

                  <div className="ap-field">
                    <label>Company Name</label>
                    <input
                      type="text"
                      value={settings?.company_name ?? ''}
                      onChange={e => handleChange('company_name', e.target.value)}
                      placeholder="Your Company Pvt. Ltd."
                    />
                  </div>

                  <div className="ap-field">
                    <label>Address</label>
                    <textarea
                      rows={3}
                      value={settings?.address ?? ''}
                      onChange={e => handleChange('address', e.target.value)}
                      placeholder="123 Industrial Area, Phase 2, City - 400001"
                    />
                  </div>

                  <div className="ap-row">
                    <div className="ap-field">
                      <label>GST Number</label>
                      <input
                        type="text"
                        value={settings?.gst_number ?? ''}
                        onChange={e => handleChange('gst_number', e.target.value)}
                        placeholder="22AAAAA0000A1Z5"
                      />
                    </div>
                    <div className="ap-field">
                      <label>Contact Info</label>
                      <input
                        type="text"
                        value={settings?.contact_info ?? ''}
                        onChange={e => handleChange('contact_info', e.target.value)}
                        placeholder="+91 98765 43210 | info@company.com"
                      />
                    </div>
                  </div>

                  <div className="ap-field">
                    <label>Company Logo</label>
                    <div className="logo-zone">
                      <div className="logo-preview-box">
                        {logoPreview ? (
                          <img src={logoPreview} alt="Company logo" className="logo-img" />
                        ) : (
                          <div className="logo-empty">
                            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                              <rect x="3" y="3" width="18" height="18" rx="2"/>
                              <circle cx="8.5" cy="8.5" r="1.5"/>
                              <polyline points="21 15 16 10 5 21"/>
                            </svg>
                            <span>No logo uploaded</span>
                          </div>
                        )}
                      </div>
                      <div className="logo-actions">
                        <button
                          className="btn-logo-upload"
                          onClick={() => logoInputRef.current?.click()}
                          disabled={logoUploading}
                        >
                          {logoUploading ? (
                            <><span className="ap-spinner-sm" /> Uploading...</>
                          ) : (
                            <>
                              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M17 8l-5-5-5 5M12 3v12"/>
                              </svg>
                              Upload Logo
                            </>
                          )}
                        </button>
                        <span className="logo-hint">PNG, JPG, SVG or WEBP</span>
                        <input
                          ref={logoInputRef}
                          type="file"
                          accept="image/png,image/jpeg,image/svg+xml,image/webp"
                          style={{ display: 'none' }}
                          onChange={handleLogoUpload}
                        />
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* ── Cost Settings ── */}
              {tab === 'costs' && (
                <div className="ap-section">
                  <div className="ap-section-title">Pricing Configuration</div>

                  <div className="ap-row">
                    <div className="ap-field">
                      <label>Price per KG <span className="unit-tag">₹/kg</span></label>
                      <input
                        type="number"
                        min="0"
                        step="0.01"
                        value={settings?.price_per_kg ?? 0}
                        onChange={e => handleChange('price_per_kg', parseFloat(e.target.value) || 0)}
                      />
                    </div>
                    <div className="ap-field">
                      <label>Price per Hour <span className="unit-tag">₹/hr</span></label>
                      <input
                        type="number"
                        min="0"
                        step="0.01"
                        value={settings?.price_per_hour ?? 0}
                        onChange={e => handleChange('price_per_hour', parseFloat(e.target.value) || 0)}
                      />
                    </div>
                  </div>

                  <div className="ap-row">
                    <div className="ap-field">
                      <label>Cutting Cost per Meter <span className="unit-tag">₹/m</span></label>
                      <input
                        type="number"
                        min="0"
                        step="0.01"
                        value={settings?.cutting_cost_per_meter ?? 0}
                        onChange={e => handleChange('cutting_cost_per_meter', parseFloat(e.target.value) || 0)}
                      />
                    </div>
                    <div className="ap-field">
                      <label>Minimum Charge <span className="unit-tag">₹</span></label>
                      <input
                        type="number"
                        min="0"
                        step="0.01"
                        value={settings?.minimum_charge ?? 0}
                        onChange={e => handleChange('minimum_charge', parseFloat(e.target.value) || 0)}
                      />
                    </div>
                  </div>

                  <div className="ap-row">
                    <div className="ap-field">
                      <label>Tax Percentage <span className="unit-tag">%</span></label>
                      <input
                        type="number"
                        min="0"
                        max="100"
                        step="0.1"
                        value={settings?.tax_percent ?? 18}
                        onChange={e => handleChange('tax_percent', parseFloat(e.target.value) || 0)}
                      />
                    </div>
                    <div className="ap-field ap-field--info">
                      <label>Calculation Preview</label>
                      <div className="calc-preview">
                        <div className="calc-row">
                          <span>1 m cut @ ₹{(settings?.cutting_cost_per_meter || 0).toFixed(2)}/m</span>
                          <span>= ₹{(settings?.cutting_cost_per_meter || 0).toFixed(2)}</span>
                        </div>
                        <div className="calc-row">
                          <span>Min charge applies when below</span>
                          <span>₹{(settings?.minimum_charge || 0).toFixed(2)}</span>
                        </div>
                        <div className="calc-row calc-row--tax">
                          <span>+ GST @ {settings?.tax_percent || 0}%</span>
                          <span>on subtotal</span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* ── Quotation Footer ── */}
              {tab === 'footer' && (
                <div className="ap-section">
                  <div className="ap-section-title">Quote Document Footer</div>

                  <div className="ap-field">
                    <label>Terms &amp; Conditions</label>
                    <textarea
                      rows={6}
                      value={settings?.terms_and_conditions ?? ''}
                      onChange={e => handleChange('terms_and_conditions', e.target.value)}
                      placeholder="1. Payment due within 30 days of invoice date.&#10;2. Prices are subject to change without notice.&#10;3. Goods once sold will not be taken back."
                    />
                  </div>

                  <div className="ap-field">
                    <label>Bank Details</label>
                    <textarea
                      rows={4}
                      value={settings?.bank_details ?? ''}
                      onChange={e => handleChange('bank_details', e.target.value)}
                      placeholder="Bank: State Bank of India&#10;Account No: 1234567890&#10;IFSC: SBIN0001234&#10;Branch: Industrial Area"
                    />
                  </div>

                  <div className="ap-field">
                    <label>Authorised Signatory Name</label>
                    <input
                      type="text"
                      value={settings?.signature_name ?? ''}
                      onChange={e => handleChange('signature_name', e.target.value)}
                      placeholder="Rajesh Kumar"
                    />
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer actions */}
        <div className="ap-footer">
          {saveMsg.text && (
            <span className={`ap-save-msg ap-save-msg--${saveMsg.type}`}>
              {saveMsg.type === 'ok' ? (
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <polyline points="20 6 9 17 4 12"/>
                </svg>
              ) : (
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
                </svg>
              )}
              {saveMsg.text}
            </span>
          )}
          <div className="ap-footer-btns">
            <button className="ap-btn-cancel" onClick={onClose}>Cancel</button>
            <button className="ap-btn-save" onClick={handleSave} disabled={saving || loading}>
              {saving ? (
                <><span className="ap-spinner-sm" /> Saving...</>
              ) : (
                <>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M19 21H5a2 2 0 01-2-2V5a2 2 0 012-2h11l5 5v11a2 2 0 01-2 2z"/>
                    <polyline points="17 21 17 13 7 13 7 21"/>
                    <polyline points="7 3 7 8 15 8"/>
                  </svg>
                  Save Settings
                </>
              )}
            </button>
          </div>
        </div>

      </div>
    </div>
  );
}
