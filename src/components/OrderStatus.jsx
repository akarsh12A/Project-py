import React, { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';

const POLL_INTERVAL = 2500; // ms

const OrderStatus = ({ orderId, onCancel, cancelError }) => {
  const [order, setOrder]     = useState(null);
  const [error, setError]     = useState('');
  const [loading, setLoading] = useState(true);
  const intervalRef           = useRef(null);

  const fetchStatus = async () => {
    try {
      const res = await fetch(`/api/orders/${orderId}`);
      if (!res.ok) throw new Error('Failed to fetch order status.');
      const data = await res.json();
      setOrder(data);
      setLoading(false);

      // Stop polling once terminal state is reached
      if (['SUCCESS', 'FAILED', 'CANCELLED'].includes(data.status)) {
        clearInterval(intervalRef.current);
      }
    } catch (err) {
      setError(err.message);
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
    intervalRef.current = setInterval(fetchStatus, POLL_INTERVAL);
    return () => clearInterval(intervalRef.current);
  }, [orderId]);

  // ── Derived state ─────────────────────────────────────────────
  const status           = order?.status || '';
  const inventoryStatus  = order?.inventory_status || '';
  const isTerminal       = ['SUCCESS', 'FAILED', 'CANCELLED'].includes(status);
  const isCancellable    = !isTerminal;
  const isLoading        = !isTerminal || loading;

  // ── Render helpers ────────────────────────────────────────────
  const bannerStyle = {
    SUCCESS:   { background: '#d1fae5', color: '#065f46', border: '1px solid #6ee7b7' },
    FAILED:    { background: '#fee2e2', color: '#991b1b', border: '1px solid #fca5a5' },
    CANCELLED: { background: '#fef3c7', color: '#92400e', border: '1px solid #fcd34d' },
  };

  const statusIcon = { SUCCESS: '✅', FAILED: '❌', CANCELLED: '⚠️', PROCESSING: '⏳', PENDING: '⏳' };

  return (
    <div className="card" style={{ maxWidth: 520, margin: '2rem auto' }}>
      <h2 style={{ marginBottom: '1rem' }}>Order #{orderId}</h2>

      {/* Error banner */}
      {error      && <div className="error-message">{error}</div>}
      {cancelError && <div className="error-message">{cancelError}</div>}

      {/* Loading spinner while PENDING / PROCESSING */}
      {(status === 'PENDING' || status === 'PROCESSING' || loading) && (
        <div style={{ textAlign: 'center', padding: '1.5rem 0' }}>
          <div className="spinner" style={{ margin: '0 auto 1rem' }}></div>
          <p style={{ color: '#6b7280' }}>
            {loading ? 'Fetching order status…' : 'Processing your order, please wait…'}
          </p>
        </div>
      )}

      {/* Terminal state banner */}
      {isTerminal && (
        <div style={{
          ...bannerStyle[status],
          borderRadius: 8,
          padding: '1rem 1.25rem',
          marginBottom: '1.25rem',
          fontSize: '1rem',
          fontWeight: 600,
        }}>
          {statusIcon[status]}&nbsp;
          {status === 'SUCCESS' && 'Order placed successfully! Your food is being prepared.'}
          {status === 'FAILED'  && (
            <>
              Item out of stock ❌<br />
              <span style={{ fontSize: '0.85rem', fontWeight: 400 }}>
                {order?.failure_reason || 'One or more items are unavailable.'}<br />
                Please remove unavailable items from your cart and try again.
              </span>
            </>
          )}
          {status === 'CANCELLED' && 'This order has been cancelled.'}
        </div>
      )}

      {/* Order Detail Grid */}
      {order && (
        <div style={{ marginBottom: '1rem', lineHeight: 1.8 }}>
          <p><strong>Overall Status:</strong>{' '}
            <span className={`status-badge ${status.toLowerCase()}`}>{status}</span>
          </p>
          <p><strong>Payment:</strong>{' '}
            <span className={`status-badge ${(order.payment_status||'').toLowerCase()}`}>
              {order.payment_status}
            </span>
          </p>
          <p><strong>Inventory:</strong>{' '}
            <span className={`status-badge ${(inventoryStatus||'').toLowerCase()}`}>
              {inventoryStatus}
            </span>
          </p>
          {order.total_amount && (
            <p><strong>Total Charged:</strong> ₹{Number(order.total_amount).toFixed(2)}</p>
          )}
          {order.items && (
            <div>
              <strong>Items:</strong>
              <ul style={{ margin: '0.25rem 0 0 1.25rem' }}>
                {order.items.map((it, i) => (
                  <li key={i}>{it.item_name} × {it.qty}
                    {it.unit_price ? ` — ₹${it.unit_price}` : ''}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Actions */}
      <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
        {isCancellable && (
          <button className="btn-danger" onClick={() => onCancel(orderId)}>
            Cancel Order
          </button>
        )}
        <Link to="/" style={{ textDecoration: 'none' }}>
          <button className="btn-primary">← Back to Menu</button>
        </Link>
        {status === 'FAILED' && (
          <Link to="/cart" style={{ textDecoration: 'none' }}>
            <button className="btn-primary">Edit Cart &amp; Retry</button>
          </Link>
        )}
      </div>
    </div>
  );
};

export default OrderStatus;
