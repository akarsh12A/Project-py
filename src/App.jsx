import { useState } from 'react';
import { Routes, Route, Link, useNavigate, useParams, Navigate } from 'react-router-dom';
import './App.css';
import ItemList from './components/ItemList';
import Cart from './components/Cart';
import OrderStatus from './components/OrderStatus';

// Menu items — item_name MUST match inventory table exactly
const MENU_ITEMS = [
  { id: 1, name: 'Classic Burger',    price: 150 },
  { id: 2, name: 'Margherita Pizza',  price: 250 },
  { id: 3, name: 'French Fries',      price: 90  },
  { id: 4, name: 'Cold Coffee',       price: 120 },
  { id: 5, name: 'Grilled Sandwich',  price: 110 },
  { id: 6, name: 'White Sauce Pasta', price: 180 },
];

const API_BASE = '/api';

function App() {
  const [quantities, setQuantities]   = useState({});
  const [isOrdering, setIsOrdering]  = useState(false);
  const [orderError, setOrderError]  = useState('');
  const [cancelError, setCancelError] = useState('');
  const navigate = useNavigate();

  const updateQuantity = (itemId, delta) => {
    setQuantities(prev => {
      const newQty = Math.max(0, (prev[itemId] || 0) + delta);
      return { ...prev, [itemId]: newQty };
    });
  };

  // ── Place Order ──────────────────────────────────────────────
  const handlePlaceOrder = async (cartItems, currentQuantities) => {
    setIsOrdering(true);
    setOrderError('');

    try {
      // Build the payload — backend calculates total_amount from DB prices
      const payload = {
        items: cartItems.map(item => ({
          item_name: item.name,
          qty: currentQuantities[item.id],
        })),
        currency: 'INR',
      };

      const idempotencyKey = crypto.randomUUID();

      const response = await fetch(`${API_BASE}/orders`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Idempotency-Key': idempotencyKey,
        },
        body: JSON.stringify(payload),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || 'Failed to place order.');
      }

      // Clear cart and go to status page
      setQuantities({});
      navigate(`/status/${data.order_id}`);
    } catch (err) {
      setOrderError(err.message || 'An error occurred while placing the order.');
    } finally {
      setIsOrdering(false);
    }
  };

  // ── Cancel Order ─────────────────────────────────────────────
  const handleCancelOrder = async (idToCancel) => {
    setCancelError('');
    try {
      const response = await fetch(`${API_BASE}/orders/${idToCancel}/cancel`, {
        method: 'POST',
      });
      if (!response.ok) throw new Error('Failed to cancel order.');
      alert('Order cancelled successfully.');
    } catch (err) {
      setCancelError(err.message || 'Error cancelling order.');
    }
  };

  const cartItemsCount = Object.values(quantities).reduce((a, b) => a + b, 0);

  return (
    <div className="app-container">
      <header>
        <h1>Food Order System</h1>
        <nav style={{ display: 'flex', gap: '1rem', justifyContent: 'center', marginTop: '1rem' }}>
          <Link to="/" style={navLinkStyle}>Menu</Link>
          <Link to="/cart" style={navLinkStyle}>
            Cart {cartItemsCount > 0 && <span style={badgeStyle}>{cartItemsCount}</span>}
          </Link>
        </nav>
      </header>

      {orderError && <div className="error-message">{orderError}</div>}

      <div className="main-content" style={{ display: 'block' }}>
        <Routes>
          <Route path="/" element={
            <ItemList items={MENU_ITEMS} quantities={quantities} updateQuantity={updateQuantity} />
          } />

          <Route path="/cart" element={
            <Cart
              items={MENU_ITEMS}
              quantities={quantities}
              onPlaceOrder={handlePlaceOrder}
              isOrdering={isOrdering}
            />
          } />

          <Route path="/status/:orderId" element={
            <OrderStatusWrapper onCancel={handleCancelOrder} cancelError={cancelError} />
          } />

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
    </div>
  );
}

function OrderStatusWrapper({ onCancel, cancelError }) {
  const { orderId } = useParams();
  if (!orderId) return <div>No Order found.</div>;
  return <OrderStatus orderId={orderId} onCancel={onCancel} cancelError={cancelError} />;
}

const navLinkStyle = {
  textDecoration: 'none',
  padding: '0.5rem 1rem',
  backgroundColor: '#e5e7eb',
  borderRadius: '0.5rem',
  color: '#374151',
  fontWeight: '600',
};

const badgeStyle = {
  backgroundColor: '#ef4444',
  color: 'white',
  padding: '0.1rem 0.4rem',
  borderRadius: '9999px',
  fontSize: '0.75rem',
  marginLeft: '0.5rem',
};

export default App;
