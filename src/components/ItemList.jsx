import React from 'react';

const ItemList = ({ items, quantities, updateQuantity }) => {
  return (
    <div className="card item-list-card">
      <h2>Menu Items</h2>
      <div className="item-list">
        {items.map((item) => (
          <div key={item.id} className="food-item">
            <div className="item-info">
              <h3>{item.name}</h3>
              <div className="price">₹{item.price}</div>
            </div>
            <div className="quantity-controls">
              <button 
                className="qty-btn"
                onClick={() => updateQuantity(item.id, -1)}
                disabled={!quantities[item.id]}
              >
                -
              </button>
              <span className="qty-display">{quantities[item.id] || 0}</span>
              <button 
                className="qty-btn"
                onClick={() => updateQuantity(item.id, 1)}
              >
                +
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default ItemList;
