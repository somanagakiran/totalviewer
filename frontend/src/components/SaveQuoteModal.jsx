import { useState } from 'react';
import './SaveQuoteModal.css';

function genQuoteNo() {
  const now  = new Date();
  const yy   = String(now.getFullYear()).slice(2);
  const mm   = String(now.getMonth() + 1).padStart(2, '0');
  const rand = Math.floor(Math.random() * 900 + 100);
  return `Q${yy}${mm}${rand}`;
}

export default function SaveQuoteModal({ onSave, onClose, prefill, clients }) {
  const [form, setForm] = useState({
    company:     prefill?.company     || '',
    quoteNo:     prefill?.quoteNo     || genQuoteNo(),
    date:        prefill?.date        || new Date().toISOString().split('T')[0],
    amount:      prefill?.amount      != null ? String(prefill.amount)      : '',
    parts:       prefill?.parts       != null ? String(prefill.parts)       : '',
    totalWeight: prefill?.totalWeight != null ? String(prefill.totalWeight) : '',
  });

  const set = (field, value) => setForm(prev => ({ ...prev, [field]: value }));

  const handleSave = () => {
    if (!form.company.trim()) { alert('Company name is required'); return; }
    if (!form.quoteNo.trim())  { alert('Quote number is required');  return; }
    onSave({
      ...form,
      amount:      parseFloat(form.amount)      || 0,
      parts:       parseInt(form.parts)          || 0,
      totalWeight: parseFloat(form.totalWeight)  || 0,
    });
  };

  return (
    <div className="sqm-backdrop" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="sqm-modal">

        <div className="sqm-header">
          <div className="sqm-header-icon">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M20.59 13.41l-7.17 7.17a2 2 0 01-2.83 0L2 12V2h10l8.59 8.59a2 2 0 010 2.82z"/>
              <line x1="7" y1="7" x2="7.01" y2="7"/>
            </svg>
          </div>
          <h2>Save Quote</h2>
          <button className="sqm-close" onClick={onClose} title="Close">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>

        <div className="sqm-body">

          <div className="sqm-field sqm-field--full">
            <label>Company <span className="sqm-req">*</span></label>
            <input
              list="sqm-companies-list"
              value={form.company}
              onChange={e => set('company', e.target.value)}
              placeholder="Type or select company name"
              autoFocus
            />
            <datalist id="sqm-companies-list">
              {(clients || []).map(c => <option key={c.id} value={c.company} />)}
            </datalist>
          </div>

          <div className="sqm-row">
            <div className="sqm-field">
              <label>Quote Number <span className="sqm-req">*</span></label>
              <input value={form.quoteNo} onChange={e => set('quoteNo', e.target.value)} />
            </div>
            <div className="sqm-field">
              <label>Date</label>
              <input type="date" value={form.date} onChange={e => set('date', e.target.value)} />
            </div>
          </div>

          <div className="sqm-row">
            <div className="sqm-field">
              <label>Amount (₹)</label>
              <input
                type="number"
                min="0"
                step="0.01"
                value={form.amount}
                onChange={e => set('amount', e.target.value)}
                placeholder="0.00"
              />
            </div>
            <div className="sqm-field">
              <label>No. of Parts</label>
              <input
                type="number"
                min="0"
                step="1"
                value={form.parts}
                onChange={e => set('parts', e.target.value)}
                placeholder="0"
              />
            </div>
          </div>

          <div className="sqm-field sqm-field--half">
            <label>Total Weight (kg)</label>
            <input
              type="number"
              min="0"
              step="0.001"
              value={form.totalWeight}
              onChange={e => set('totalWeight', e.target.value)}
              placeholder="0.000"
            />
          </div>

        </div>

        <div className="sqm-footer">
          <button className="sqm-btn sqm-btn--cancel" onClick={onClose}>Cancel</button>
          <button className="sqm-btn sqm-btn--save" onClick={handleSave}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M19 21H5a2 2 0 01-2-2V5a2 2 0 012-2h11l5 5v11a2 2 0 01-2 2z"/>
              <polyline points="17 21 17 13 7 13 7 21"/>
              <polyline points="7 3 7 8 15 8"/>
            </svg>
            Save Quote
          </button>
        </div>

      </div>
    </div>
  );
}
