import React from 'react';

const Cart = ({ items, quantities, onPlaceOrder, isOrdering }) => {
  // Calculate cart items and total amount
  const cartItems = items.filter(item => quantities[item.id] > 0);
  const totalAmount = cartItems.reduce((sum, item) => sum + (item.price * quantities[item.id]), 0);

  return (
    <div className="card cart-card">
      <h2>Your Cart</h2>
      
      {cartItems.length === 0 ? (
        <p style={{ color: '#6b7280', textAlign: 'center', padding: '1rem 0' }}>Your cart is empty</p>
      ) : (
        <>
          <div className="cart-items">
            {cartItems.map(item => (
              <div key={item.id} className="cart-item">
                <span>{item.name} x {quantities[item.id]}</span>
                <span>₹{item.price * quantities[item.id]}</span>
              </div>
            ))}
          </div>
          
          <div className="cart-total">
            <span>Total:</span>
            <span>₹{totalAmount}</span>
          </div>

          <button 
            className="btn-primary" 
            onClick={() => onPlaceOrder(cartItems, quantities)}
            disabled={isOrdering}
          >
            {isOrdering ? 'Placing Order…' : 'Place Order'}
          </button>
        </>
      )}
    </div>
  );
};

export default Cart;
