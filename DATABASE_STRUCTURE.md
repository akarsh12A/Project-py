# Database Structure & Relationships Documentation

## 📋 Table of Contents
1. [Database Overview](#database-overview)
2. [Schema Design](#schema-design)
3. [Table Definitions](#table-definitions)
4. [Relationships & Constraints](#relationships--constraints)
5. [Indexes](#indexes)
6. [SQL Scripts](#sql-scripts)
7. [Data Flow](#data-flow)
8. [Concurrency Handling](#concurrency-handling)
9. [Redis Integration](#redis-integration)
10. [Celery Integration](#celery-integration)

---

## 🏗️ Database Overview

### Database Information
- **Name**: `order_system`
- **Type**: MySQL 5.7+
- **Character Set**: utf8mb4
- **Collation**: utf8mb4_unicode_ci
- **Engine**: InnoDB (for ACID compliance)

### Tables
| Table | Records | Purpose | Type |
|-------|---------|---------|------|
| orders | Variable | Order transactions | Core |
| inventory | Low | Product catalog | Reference |
| order_logs | High | Audit trail | Logging |

### Characteristics
- ✅ ACID compliant (InnoDB)
- ✅ Atomic transactions
- ✅ Foreign key constraints
- ✅ Comprehensive indexing
- ✅ JSON support for flexible data
- ✅ Timestamp tracking
- ✅ Soft deletes support (via is_cancelled)

---

## 🎯 Schema Design

### ER Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         DATABASE: order_system                  │
└─────────────────────────────────────────────────────────────────┘

┌────────────────────────────┐        ┌──────────────────────────┐
│       ORDERS TABLE         │        │   INVENTORY TABLE        │
├────────────────────────────┤        ├──────────────────────────┤
│ PK │ id (INT)             │◄───────┤ PK │ id (INT)           │
│    │ user_id (INT)        │ ╱─────►│    │ item_name (VARCHAR)│
│    │ items (JSON)         │╱       │    │ stock_quantity(INT)│
│    │ total_amount (FLOAT) │        │    │ price (DECIMAL)    │
│    │ currency (VARCHAR)   │        │    │ updated_at(DATETIME)│
│    │ status (VARCHAR)     │        └──────────────────────────┘
│    │ payment_status (V)   │
│    │ inventory_status (V) │
│    │ retry_count (INT)    │
│    │ idempotency_key (V)  │
│    │ razorpay_* (VARCHAR) │
│    │ failure_reason (TEXT)│
│    │ is_cancelled (BOOL)  │
│    │ cancelled_at (DT)    │
│    │ created_at (DT)      │
│    │ updated_at (DT)      │
└────────────────────────────┘
         △
         │ (order_id FK)
         │
┌────────┴───────────────────┐
│    ORDER_LOGS TABLE        │
├────────────────────────────┤
│ PK │ id (INT)             │
│    │ order_id (INT FK)    │
│    │ event (VARCHAR)      │
│    │ message (TEXT)       │
│    │ created_at (DATETIME)│
└────────────────────────────┘
```

---

## 📊 Table Definitions

### 1. ORDERS Table

**Purpose**: Core transaction table storing all order information with comprehensive state tracking.

**Schema:**
```sql
CREATE TABLE orders (
  id INT PRIMARY KEY AUTO_INCREMENT COMMENT 'Unique order identifier',
  
  user_id INT COMMENT 'User who placed the order',
  
  items JSON NOT NULL COMMENT 'Array of items: [{"item_name":"...", "qty":..., "unit_price":...}]',
  total_amount FLOAT NOT NULL COMMENT 'Total order value in specified currency',
  currency VARCHAR(10) DEFAULT 'INR' COMMENT 'Currency code (INR, USD, EUR, etc.)',
  
  status VARCHAR(20) DEFAULT 'PENDING' COMMENT 'Order status: PENDING|PROCESSING|SUCCESS|FAILED|CANCELLED',
  payment_status VARCHAR(20) DEFAULT 'PENDING' COMMENT 'Payment status: PENDING|SUCCESS|FAILED',
  inventory_status VARCHAR(20) DEFAULT 'PENDING' COMMENT 'Inventory status: PENDING|RESERVED|FAILED',
  
  retry_count INT DEFAULT 0 COMMENT 'Number of retry attempts (max 3)',
  last_retry_at DATETIME COMMENT 'Timestamp of last retry attempt',
  
  idempotency_key VARCHAR(100) UNIQUE COMMENT 'Ensures duplicate request prevention',
  
  razorpay_order_id VARCHAR(255) COMMENT 'External payment gateway order ID',
  razorpay_payment_id VARCHAR(255) COMMENT 'External payment gateway payment ID',
  razorpay_signature VARCHAR(255) COMMENT 'Razorpay webhook signature verification',
  
  failure_reason TEXT COMMENT 'Human-readable failure reason',
  is_cancelled BOOLEAN DEFAULT FALSE COMMENT 'Soft delete flag for cancellation',
  cancelled_at DATETIME COMMENT 'When order was cancelled',
  
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT 'Order creation timestamp',
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Last modification timestamp',
  
  ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
) COMMENT='Order transaction records with comprehensive state tracking';
```

**Column Details:**

| Column | Type | Size | NULL | Key | Default | Description |
|--------|------|------|------|-----|---------|-------------|
| id | INT | 11 | NO | PK | AUTO_INCREMENT | Unique order identifier |
| user_id | INT | 11 | YES | | NULL | References user; nullable |
| items | JSON | - | NO | | - | Structured item data |
| total_amount | FLOAT | - | NO | | - | Order amount |
| currency | VARCHAR | 10 | YES | | 'INR' | Currency code |
| status | VARCHAR | 20 | YES | | 'PENDING' | Order workflow status |
| payment_status | VARCHAR | 20 | YES | | 'PENDING' | Payment processing status |
| inventory_status | VARCHAR | 20 | YES | | 'PENDING' | Stock reservation status |
| retry_count | INT | 11 | YES | | 0 | Celery retry counter |
| last_retry_at | DATETIME | - | YES | | NULL | Last retry timestamp |
| idempotency_key | VARCHAR | 100 | YES | UQ | NULL | Deduplication key |
| razorpay_order_id | VARCHAR | 255 | YES | | NULL | Payment gateway ref |
| razorpay_payment_id | VARCHAR | 255 | YES | | NULL | Payment ID |
| razorpay_signature | VARCHAR | 255 | YES | | NULL | Webhook signature |
| failure_reason | TEXT | - | YES | | NULL | Error message |
| is_cancelled | BOOLEAN | 1 | YES | | FALSE | Cancellation flag |
| cancelled_at | DATETIME | - | YES | | NULL | Cancellation time |
| created_at | DATETIME | - | YES | | NOW() | Creation timestamp |
| updated_at | DATETIME | - | YES | | NOW() | Update timestamp |

**Status State Machine:**
```
PENDING ──────► PROCESSING ──────► SUCCESS
                     │                ▲
                     ├─► FAILED ──────┤
                     │                │
                     └─► CANCELLED ───┘

Payment Status Flow:
PENDING ──────► SUCCESS / FAILED

Inventory Status Flow:
PENDING ──────► RESERVED / FAILED
```

---

### 2. INVENTORY Table

**Purpose**: Product catalog with stock management and atomic update support.

**Schema:**
```sql
CREATE TABLE inventory (
  id INT PRIMARY KEY AUTO_INCREMENT COMMENT 'Unique inventory item ID',
  
  item_name VARCHAR(100) UNIQUE NOT NULL COMMENT 'Product name (matches order items)',
  stock_quantity INT DEFAULT 0 COMMENT 'Current available quantity',
  price DECIMAL(10, 2) COMMENT 'Unit price for order calculations',
  
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Stock update timestamp',
  
  ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
) COMMENT='Inventory catalog with atomic stock management';
```

**Column Details:**

| Column | Type | Size | NULL | Key | Default | Description |
|--------|------|------|------|-----|---------|-------------|
| id | INT | 11 | NO | PK | AUTO_INCREMENT | Unique inventory ID |
| item_name | VARCHAR | 100 | NO | UQ | - | Product identifier |
| stock_quantity | INT | 11 | YES | | 0 | Available stock |
| price | DECIMAL | 10,2 | YES | | NULL | Unit price |
| updated_at | DATETIME | - | YES | | NOW() | Last update time |

**Sample Data:**
```sql
INSERT INTO inventory (item_name, stock_quantity, price) VALUES
  ('Laptop', 50, 99999.00),
  ('Mouse', 200, 999.00),
  ('Keyboard', 150, 1499.00),
  ('Monitor', 30, 19999.00),
  ('USB Cable', 500, 299.00),
  ('Headphones', 100, 3999.00),
  ('Webcam', 75, 2499.00),
  ('Hard Drive 1TB', 40, 4999.00),
  ('SSD 512GB', 60, 6999.00),
  ('RAM 8GB', 80, 3499.00);
```

**Stock Update Query (Atomic - Race Condition Safe):**
```sql
UPDATE inventory 
SET stock_quantity = stock_quantity - :qty 
WHERE item_name = :name AND stock_quantity >= :qty;

-- Check result:
-- rowcount > 0: SUCCESS (stock was reserved)
-- rowcount = 0: FAILURE (item not found or insufficient stock)
```

---

### 3. ORDER_LOGS Table

**Purpose**: Comprehensive audit trail for order lifecycle and debugging.

**Schema:**
```sql
CREATE TABLE order_logs (
  id INT PRIMARY KEY AUTO_INCREMENT COMMENT 'Log entry ID',
  
  order_id INT NOT NULL COMMENT 'References orders.id (parent order)',
  event VARCHAR(100) NOT NULL COMMENT 'Event type/category',
  message TEXT COMMENT 'Detailed event description',
  
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT 'Log timestamp',
  
  ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci,
  FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
) COMMENT='Order event audit trail and debug logs';
```

**Column Details:**

| Column | Type | Size | NULL | Key | Default | Description |
|--------|------|------|------|-----|---------|-------------|
| id | INT | 11 | NO | PK | AUTO_INCREMENT | Log entry ID |
| order_id | INT | 11 | NO | FK | - | Reference to order |
| event | VARCHAR | 100 | NO | | - | Event type |
| message | TEXT | - | YES | | NULL | Event description |
| created_at | DATETIME | - | YES | | NOW() | Log timestamp |

**Event Types:**

| Event | Trigger | Description |
|-------|---------|-------------|
| ORDER_CREATED | Create Order API | Order successfully created in database |
| PROCESSING_STARTED | Celery Task Start | Worker begins processing order |
| PAYMENT_STARTED | Phase 2 Begin | Simulating payment gateway call |
| PAYMENT_FAILED | Payment Decline | Payment gateway simulation failed |
| PAYMENT_SUCCESS | Payment Accept | Payment processing successful |
| INVENTORY_CHECK_STARTED | Phase 5 Begin | Starting atomic stock validation |
| INVENTORY_RESERVED | Stock Check Pass | All items reserved successfully |
| INVENTORY_FAILED | Stock Check Fail | Out of stock detected |
| ORDER_CANCELLED | User Request/Task | Order cancelled by user or system |
| ORDER_SUCCESS | All Phases Pass | Order completed successfully |
| ORDER_FAILED | Fatal Error | Order failed permanently |

**Sample Log Entry:**
```json
{
  "id": 1,
  "order_id": 5,
  "event": "ORDER_CREATED",
  "message": "Order created with calculated total: 204995.00",
  "created_at": "2026-05-19 10:30:45"
}
```

---

## 🔗 Relationships & Constraints

### 1. Orders ↔ Inventory (Implicit via JSON)

**Type**: Many-to-Many (implicit)

**Relationship:**
```
Order.items = [
  {
    "item_name": "Laptop",      ◄─── Validated against inventory.item_name
    "qty": 2,
    "unit_price": 99999.00      ◄─── Fetched from inventory.price
  },
  {
    "item_name": "Mouse",
    "qty": 3,
    "unit_price": 999.00
  }
]
```

**Validation Logic:**
```python
def create_order(user_id, items, currency, idempotency_key):
    calculated_total = 0.0
    validated_items = []
    
    for item in items:
        item_name = item.get('item_name')
        qty = item.get('qty', 0)
        
        # Check item exists in inventory
        inv = Inventory.query.filter_by(item_name=item_name).first()
        if not inv:
            raise ValueError(f"Item '{item_name}' not found")
        
        # Fetch unit price from database
        item_total = float(inv.price) * qty
        calculated_total += item_total
        
        # Store validated item with unit price
        validated_items.append({
            "item_name": item_name,
            "qty": qty,
            "unit_price": float(inv.price)
        })
    
    # Create order with validated data
    order = Order(items=validated_items, total_amount=calculated_total, ...)
```

**Constraints:**
- Item must exist in inventory.item_name
- Item must have a price configured
- Quantity must be positive integer
- Price cannot be null

---

### 2. Orders ← OrderLogs (1:Many)

**Type**: One-to-Many

**Schema:**
```
orders
  ├─ id (PK)
  │
  └─ ◄──── order_logs
           ├─ order_id (FK) → orders.id
           ├─ event
           └─ message
```

**SQL Representation:**
```sql
ALTER TABLE order_logs 
ADD CONSTRAINT fk_order_logs_order_id 
FOREIGN KEY (order_id) 
REFERENCES orders(id) 
ON DELETE CASCADE;
```

**Cascade Behavior:**
- When an order is deleted, all associated logs are automatically deleted
- When an order is updated, logs remain unchanged (append-only)

**Query Example:**
```sql
-- Get all events for an order
SELECT * FROM order_logs 
WHERE order_id = 5 
ORDER BY created_at ASC;

-- Timeline view
SELECT 
  ol.event,
  ol.message,
  ol.created_at,
  TIMESTAMPDIFF(SECOND, LAG(ol.created_at) OVER (ORDER BY ol.created_at), ol.created_at) as duration_secs
FROM order_logs ol
WHERE ol.order_id = 5
ORDER BY ol.created_at ASC;
```

---

### 3. Orders self-referential (Idempotency)

**Type**: Natural Key (Idempotency-Key)

**Purpose**: Prevent duplicate order creation

**Implementation:**
```python
# On request 1
def create_order(..., idempotency_key):
    existing = Order.query.filter_by(idempotency_key=idempotency_key).first()
    if existing:
        return existing  # Return cached result
    
    order = Order(..., idempotency_key=idempotency_key)
    db.session.add(order)
    db.session.commit()
    return order

# Request 2 with same idempotency_key will return same order (idempotent)
```

---

## 📑 Indexes

### Index Strategy

**Purpose**: Optimize query performance and maintain data integrity

### Index Definitions

#### orders table
```sql
-- Primary Key (Implicit)
CREATE UNIQUE INDEX pk_orders ON orders(id);

-- Foreign Key / Relationship
CREATE INDEX idx_user_id ON orders(user_id) COMMENT 'Query orders by user';

-- Status Filters (Search)
CREATE INDEX idx_status ON orders(status) COMMENT 'Filter by order status';
CREATE INDEX idx_payment_status ON orders(payment_status) COMMENT 'Filter by payment status';
CREATE INDEX idx_inventory_status ON orders(inventory_status) COMMENT 'Filter by inventory status';

-- Temporal Queries (Analytics)
CREATE INDEX idx_created_at ON orders(created_at) COMMENT 'Range queries on creation date';

-- Deduplication (Idempotency)
CREATE UNIQUE INDEX idx_idempotency_key ON orders(idempotency_key) COMMENT 'Ensure unique idempotency keys';

-- Composite Indexes (Optimized queries)
CREATE INDEX idx_user_status_date ON orders(user_id, status, created_at);
CREATE INDEX idx_status_date ON orders(status, created_at DESC);
```

#### inventory table
```sql
-- Primary Key (Implicit)
CREATE UNIQUE INDEX pk_inventory ON inventory(id);

-- Natural Key (Product lookup)
CREATE UNIQUE INDEX idx_item_name ON inventory(item_name) COMMENT 'Fast product lookup';

-- Stock queries
CREATE INDEX idx_stock_quantity ON inventory(stock_quantity) COMMENT 'Low stock queries';
```

#### order_logs table
```sql
-- Primary Key (Implicit)
CREATE UNIQUE INDEX pk_order_logs ON order_logs(id);

-- Foreign Key (Relationship)
CREATE INDEX idx_order_id ON order_logs(order_id) COMMENT 'Get logs for order';

-- Event queries
CREATE INDEX idx_event ON order_logs(event) COMMENT 'Filter by event type';

-- Temporal queries
CREATE INDEX idx_created_at ON order_logs(created_at) COMMENT 'Range queries on log date';

-- Composite Index (Most common query)
CREATE INDEX idx_order_event_date ON order_logs(order_id, event, created_at);
```

### Index Performance Impact

| Index | Columns | Cardinality | Size | Maintenance |
|-------|---------|-------------|------|-------------|
| idx_user_id | orders.user_id | Medium | Small | Low |
| idx_status | orders.status | Low (5 values) | Small | Low |
| idx_created_at | orders.created_at | High | Medium | Low |
| idx_idempotency_key | orders.idempotency_key | High | Medium | Medium |
| idx_item_name | inventory.item_name | High | Small | Low |
| idx_order_id | order_logs.order_id | High | Medium | Medium |

---

## 📝 SQL Scripts

### 1. Database Initialization

```sql
-- Create Database
CREATE DATABASE IF NOT EXISTS order_system 
CHARACTER SET utf8mb4 
COLLATE utf8mb4_unicode_ci;

USE order_system;

-- Create tables
CREATE TABLE IF NOT EXISTS orders (
  id INT PRIMARY KEY AUTO_INCREMENT,
  user_id INT,
  items JSON NOT NULL,
  total_amount FLOAT NOT NULL,
  currency VARCHAR(10) DEFAULT 'INR',
  status VARCHAR(20) DEFAULT 'PENDING',
  payment_status VARCHAR(20) DEFAULT 'PENDING',
  inventory_status VARCHAR(20) DEFAULT 'PENDING',
  retry_count INT DEFAULT 0,
  last_retry_at DATETIME,
  idempotency_key VARCHAR(100) UNIQUE,
  razorpay_order_id VARCHAR(255),
  razorpay_payment_id VARCHAR(255),
  razorpay_signature VARCHAR(255),
  failure_reason TEXT,
  is_cancelled BOOLEAN DEFAULT FALSE,
  cancelled_at DATETIME,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_user_id (user_id),
  INDEX idx_status (status),
  INDEX idx_payment_status (payment_status),
  INDEX idx_inventory_status (inventory_status),
  INDEX idx_created_at (created_at),
  UNIQUE INDEX idx_idempotency_key (idempotency_key),
  ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
);

CREATE TABLE IF NOT EXISTS inventory (
  id INT PRIMARY KEY AUTO_INCREMENT,
  item_name VARCHAR(100) UNIQUE NOT NULL,
  stock_quantity INT DEFAULT 0,
  price DECIMAL(10,2),
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_stock_quantity (stock_quantity),
  ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
);

CREATE TABLE IF NOT EXISTS order_logs (
  id INT PRIMARY KEY AUTO_INCREMENT,
  order_id INT NOT NULL,
  event VARCHAR(100) NOT NULL,
  message TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_order_id (order_id),
  INDEX idx_event (event),
  INDEX idx_created_at (created_at),
  FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
  ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
);
```

### 2. Sample Data Insertion

```sql
-- Insert inventory items
INSERT INTO inventory (item_name, stock_quantity, price) VALUES
('Laptop', 50, 99999.00),
('Mouse', 200, 999.00),
('Keyboard', 150, 1499.00),
('Monitor', 30, 19999.00),
('USB Cable', 500, 299.00),
('Headphones', 100, 3999.00),
('Webcam', 75, 2499.00),
('Hard Drive 1TB', 40, 4999.00),
('SSD 512GB', 60, 6999.00),
('RAM 8GB', 80, 3499.00);

-- Verify insertion
SELECT * FROM inventory;
```

### 3. Common Queries

#### Get Order with Full Details
```sql
SELECT 
  o.*,
  COUNT(ol.id) as log_count
FROM orders o
LEFT JOIN order_logs ol ON o.id = ol.order_id
WHERE o.id = ?
GROUP BY o.id;
```

#### Get Order Timeline
```sql
SELECT 
  o.id,
  o.status,
  o.total_amount,
  ol.event,
  ol.message,
  ol.created_at,
  TIMESTAMPDIFF(SECOND, 
    LAG(ol.created_at) OVER (ORDER BY ol.created_at), 
    ol.created_at) as phase_duration_secs
FROM orders o
LEFT JOIN order_logs ol ON o.id = ol.order_id
WHERE o.id = ?
ORDER BY ol.created_at ASC;
```

#### Get Failed Orders with Reason
```sql
SELECT 
  id,
  user_id,
  total_amount,
  status,
  failure_reason,
  retry_count,
  created_at
FROM orders
WHERE status = 'FAILED'
ORDER BY created_at DESC
LIMIT 100;
```

#### Get Orders by Status
```sql
SELECT 
  id,
  user_id,
  total_amount,
  status,
  payment_status,
  inventory_status,
  created_at
FROM orders
WHERE status IN ('SUCCESS', 'PENDING')
  AND created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
ORDER BY created_at DESC;
```

#### Inventory Stock Report
```sql
SELECT 
  item_name,
  stock_quantity,
  price,
  (stock_quantity * price) as total_value,
  CASE 
    WHEN stock_quantity < 10 THEN 'LOW'
    WHEN stock_quantity < 50 THEN 'MEDIUM'
    ELSE 'HIGH'
  END as stock_level,
  updated_at
FROM inventory
ORDER BY stock_quantity ASC;
```

#### Orders by User
```sql
SELECT 
  o.id,
  o.total_amount,
  o.status,
  o.created_at,
  COUNT(ol.id) as events
FROM orders o
LEFT JOIN order_logs ol ON o.id = ol.order_id
WHERE o.user_id = ?
GROUP BY o.id
ORDER BY o.created_at DESC;
```

#### Order Success Rate
```sql
SELECT 
  DATE(created_at) as date,
  COUNT(*) as total_orders,
  SUM(CASE WHEN status = 'SUCCESS' THEN 1 ELSE 0 END) as successful,
  SUM(CASE WHEN status = 'FAILED' THEN 1 ELSE 0 END) as failed,
  SUM(CASE WHEN status = 'CANCELLED' THEN 1 ELSE 0 END) as cancelled,
  ROUND(SUM(CASE WHEN status = 'SUCCESS' THEN 1 ELSE 0 END) * 100 / COUNT(*), 2) as success_rate
FROM orders
GROUP BY DATE(created_at)
ORDER BY date DESC;
```

---

## 🔄 Data Flow

### Order Creation Flow

```
API Request: POST /api/orders
    │
    ▼
[Extract Headers & Body]
    │ - Idempotency-Key
    │ - user_id, items, currency
    │
    ▼
[Service: create_order()]
    │
    ├─► [Check Idempotency]
    │   └─ Query: SELECT * FROM orders WHERE idempotency_key = ?
    │   └─ If exists: RETURN existing order (idempotent)
    │
    ├─► [Validate & Enrich Items]
    │   └─ FOR EACH item:
    │       ├─ Query: SELECT * FROM inventory WHERE item_name = ?
    │       ├─ Verify item exists & has price
    │       ├─ Fetch unit_price from database
    │       └─ Calculate item total
    │
    ├─► [Calculate Total]
    │   └─ Sum all item totals
    │   └─ Format to 2 decimals
    │
    ├─► [Create Order Record]
    │   └─ INSERT INTO orders VALUES(...)
    │       - status = 'PENDING'
    │       - payment_status = 'SUCCESS'
    │       - inventory_status = 'PENDING'
    │   └─ COMMIT transaction
    │
    ├─► [Log Event]
    │   └─ INSERT INTO order_logs (order_id, event, message)
    │
    ├─► [Trigger Celery Task]
    │   └─ process_order_task.delay(order_id)
    │   └─ Task pushed to Redis Queue
    │
    └─► [Return Response]
        └─ status: 200 OK
        └─ body: {order_id, total_amount, status, ...}
```

### Order Processing Flow (Celery Worker)

```
[Celery Worker receives message]
    │ Task: process_order_task(order_id)
    │
    ▼
[PHASE 1: Guard Checks]
    │
    ├─► [Fetch Order]
    │   └─ SELECT * FROM orders WHERE id = ?
    │
    ├─► [Check if Cancelled]
    │   └─ IF is_cancelled = TRUE: EXIT (log event)
    │
    ├─► [Check if Terminal]
    │   └─ IF status IN ('SUCCESS', 'FAILED', 'CANCELLED'): EXIT
    │
    └─► [Check Max Retries]
        └─ IF retry_count >= 3: Set status=FAILED, EXIT
    
    ▼
[PHASE 2: Payment Processing]
    │
    ├─► [Simulate Payment]
    │   └─ 30% random failure chance
    │
    ├─ IF FAILED:
    │  ├─ INCREMENT retry_count
    │  ├─ SET last_retry_at = NOW()
    │  ├─ SET failure_reason = "Payment declined"
    │  ├─ COMMIT
    │  ├─ LOG event: PAYMENT_FAILED
    │  └─ RETRY task (countdown=5 seconds, max_retries=3)
    │
    └─ IF SUCCESS:
       ├─ SET payment_status = 'SUCCESS'
       ├─ COMMIT
       └─ LOG event: PAYMENT_SUCCESS
    
    ▼
[PHASE 3: Check Cancellation]
    │
    ├─► [Re-fetch Order]
    │   └─ SELECT * FROM orders WHERE id = ?
    │
    └─► IF cancelled: EXIT (log event)
    
    ▼
[PHASE 4: Inventory Check]
    │
    ├─ IF inventory_status = 'RESERVED': 
    │  └─ Already reserved on retry, skip to success
    │
    └─ FOR EACH item in order:
       │
       ├─► [Atomic Stock Update]
       │   └─ UPDATE inventory SET stock_quantity = stock_quantity - qty
       │       WHERE item_name = ? AND stock_quantity >= qty
       │
       ├─ IF rowcount > 0: 
       │  └─ Stock reserved for this item
       │
       └─ IF rowcount = 0:
          ├─ Item not found OR insufficient stock
          ├─ ROLLBACK all updates
          ├─ SET status = 'FAILED'
          ├─ SET inventory_status = 'FAILED'
          ├─ SET failure_reason = "Out of stock: {item_name}"
          ├─ COMMIT
          ├─ LOG event: INVENTORY_FAILED
          └─ EXIT (NO RETRY - out of stock is permanent)
    
    ▼
[PHASE 5: Success]
    │
    ├─ SET inventory_status = 'RESERVED'
    ├─ SET status = 'SUCCESS'
    ├─ COMMIT
    ├─ LOG event: INVENTORY_RESERVED
    ├─ LOG event: ORDER_SUCCESS
    └─ Return (Task complete)
```

---

## 🔒 Concurrency Handling

### Problem: Race Conditions in Stock Updates

**Scenario**: Multiple simultaneous orders for same item

```
Order 1: Buy 10 Laptops (stock = 5)
Order 2: Buy 10 Laptops (stock = 5)
Order 3: Buy 10 Laptops (stock = 5)

Without Atomic Update:
1. Order 1 SELECT stock (5)
2. Order 2 SELECT stock (5)
3. Order 3 SELECT stock (5)
4. Order 1 UPDATE stock = 5 - 10 = -5 ✗ NEGATIVE!
5. Order 2 UPDATE stock = -5 - 10 = -15 ✗ OVERSELLING!
6. Order 3 UPDATE stock = -15 - 10 = -25 ✗ DISASTER!
```

### Solution: Atomic SQL UPDATE

**Implementation**:
```sql
UPDATE inventory 
SET stock_quantity = stock_quantity - :qty 
WHERE item_name = :name AND stock_quantity >= :qty;

-- In Python:
result = db.session.execute(sql, {"qty": qty, "name": item_name})

if result.rowcount == 0:
    # No rows updated = out of stock or doesn't exist
    ROLLBACK and FAIL
elif result.rowcount > 0:
    # Exactly one row updated = stock reserved
    COMMIT
```

**With Atomic Update**:
```
Order 1: UPDATE ... WHERE stock >= 10
  └─ rowcount = 0 (stock = 5 < 10) → FAIL, ROLLBACK
  
Order 2: UPDATE ... WHERE stock >= 10
  └─ rowcount = 0 (stock = 5 < 10) → FAIL, ROLLBACK
  
Order 3: UPDATE ... WHERE stock >= 10
  └─ rowcount = 0 (stock = 5 < 10) → FAIL, ROLLBACK

Result: All orders fail safely, stock = 5 (unchanged) ✓
```

### Transaction Isolation

**Configuration** (MySQL):
```sql
SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ;
```

**Isolation Levels Used**:
- **REPEATABLE READ**: Default for InnoDB
  - Prevents dirty reads
  - Prevents non-repeatable reads
  - Allows phantom reads (OK for inventory checks)

### Lock Strategy

```
Order 1 Process:
├─ BEGIN TRANSACTION
├─ SELECT order (no lock)
├─ UPDATE inventory (row-level X lock acquired)
│  └─ Blocks other transactions updating same row
├─ COMMIT
└─ Lock released

Order 2 (if simultaneous):
├─ BEGIN TRANSACTION
├─ SELECT order (no lock)
├─ UPDATE inventory (waits for Order 1's lock)
│  └─ Order 1 completes, lock released
│  └─ Order 2 acquires lock
├─ COMMIT
└─ Lock released
```

---

## 🔴 Redis Integration

### Redis Data Structures Used

#### 1. Message Queue (Celery Broker)
```
Key: celery
Type: List
Structure: [task_message_1, task_message_2, ...]

Example Task Message:
{
  "task": "app.tasks.process_order_task",
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "args": [1],  // order_id
  "kwargs": {},
  "retries": 0,
  "eta": "2026-05-19T10:30:45",
  "expires": null
}
```

#### 2. Result Backend
```
Key: celery-task-meta-{task_id}
Type: String (JSON)
TTL: 1 day (configurable)

Example Result:
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "SUCCESS",
  "result": null,
  "traceback": null,
  "children": [],
  "date_done": "2026-05-19T10:30:50"
}
```

### Redis Configuration

**File**: `backend/app/config.py`

```python
# Celery Configuration
broker_url = 'redis://localhost:6379/0'
result_backend = 'redis://localhost:6379/0'
broker_connection_retry_on_startup = True

# Task Serialization
celery_task_serializer = 'json'
celery_result_serializer = 'json'
celery_accept_content = ['json']
celery_timezone = 'UTC'
celery_enable_utc = True
```

### Redis Commands for Monitoring

```bash
# Connect to Redis CLI
redis-cli

# View all keys
KEYS *

# Check queue length
LLEN celery

# View queue contents (first 10 items)
LRANGE celery 0 10

# View specific task result
GET celery-task-meta-{task_id}

# Monitor all Redis commands in real-time
MONITOR

# Get Redis statistics
INFO

# Clear specific key
DEL key_name

# Flush all data (DANGEROUS!)
FLUSHALL

# Set key expiration
EXPIRE key_name 3600  # 1 hour

# View remaining TTL
TTL key_name
```

### Redis Data Flow

```
┌─────────────────┐
│  Flask API      │
│  (Main Thread)  │
└────────┬────────┘
         │
         │ delay(order_id)
         │
         ▼
    ┌─────────────────────────────────────┐
    │     Redis (localhost:6379)          │
    ├─────────────────────────────────────┤
    │ [Celery Broker - Message Queue]     │
    │                                     │
    │ LIST: celery                        │
    │ ├─ Task 1: process_order_task(1)   │
    │ ├─ Task 2: process_order_task(2)   │
    │ └─ Task 3: process_order_task(3)   │
    │                                     │
    │ [Result Backend - Task Results]    │
    │                                     │
    │ KEY: celery-task-meta-uuid1        │
    │ KEY: celery-task-meta-uuid2        │
    │ KEY: celery-task-meta-uuid3        │
    └─────────────────────────────────────┘
         ▲
         │ LPOP (fetch task)
         │ SET result (store result)
         │
    ┌────┴──────────────────────────────┐
    │   Celery Worker Process(es)       │
    │                                    │
    │  ┌─────────────────────────────┐  │
    │  │ Worker 1                    │  │
    │  │ - process_order_task(1) ... │  │
    │  └─────────────────────────────┘  │
    │                                    │
    │  ┌─────────────────────────────┐  │
    │  │ Worker 2                    │  │
    │  │ - process_order_task(2) ... │  │
    │  └─────────────────────────────┘  │
    │                                    │
    │  ┌─────────────────────────────┐  │
    │  │ Worker 3                    │  │
    │  │ - process_order_task(3) ... │  │
    │  └─────────────────────────────┘  │
    └────────────────────────────────────┘
```

---

## 🎯 Celery Integration

### Celery Task Definition

**File**: `backend/app/tasks.py`

```python
@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def process_order_task(self, order_id):
    """
    Full order processing pipeline with retry logic.
    
    Args:
        self: Celery task context (for retries)
        order_id: Order ID to process
        
    Returns:
        None (updates database)
        
    Retries:
        Up to 3 times on payment failure (5s delay)
        
    No Retries:
        Out of stock (permanent failure)
    """
```

### Task Configuration

| Setting | Value | Purpose |
|---------|-------|---------|
| bind | True | Access to task context (self) |
| max_retries | 3 | Maximum retry attempts |
| default_retry_delay | 5 | Delay between retries (seconds) |
| shared_task | True | Can be called from anywhere |

### Retry Logic

```python
# Retry with exponential backoff
raise self.retry(
    exc=Exception(failure_reason),
    countdown=5,      # Wait 5 seconds
    max_retries=3     # Max 3 attempts
)

# On max retries exceeded
except self.MaxRetriesExceededError:
    order.status = 'FAILED'
    db.session.commit()
```

### Task Status Tracking

```
In Redis Result Backend:
{
  "task_id": "uuid",
  "status": "PENDING" → "PROGRESS" → "SUCCESS"/"FAILURE"/"RETRY",
  "result": {...},
  "traceback": null/error_traceback,
  "children": [],
  "date_done": timestamp
}
```

### Monitoring Celery Tasks

```python
# From Flask application
from celery.result import AsyncResult

# Get task status
task_id = "uuid"
result = AsyncResult(task_id, app=celery)
print(result.state)  # PENDING, STARTED, SUCCESS, FAILURE, RETRY
print(result.result)  # Task result or error
print(result.traceback)  # Exception traceback if failed
```

---

## 📊 Summary

### Database Architecture
- **Type**: MySQL (InnoDB)
- **Tables**: 3 (orders, inventory, order_logs)
- **Relationships**: Implicit (JSON), Foreign Key, Idempotency
- **Transactions**: ACID compliant
- **Concurrency**: Atomic operations, row-level locks

### Integration Points
- **Flask**: Direct SQLAlchemy ORM
- **Celery**: Task queue with Redis
- **Redis**: Message broker & result backend
- **Logging**: Event-sourced via order_logs table

### Key Features
✅ Race condition prevention via atomic SQL
✅ Comprehensive audit trail via order_logs
✅ Idempotent API via idempotency_key
✅ Retry logic with exponential backoff
✅ Soft deletes via is_cancelled flag
✅ JSON for flexible item structure
✅ Proper indexing for performance
✅ Cascade deletes for data integrity

---

**Document Version**: 1.0.0
**Last Updated**: 2026-05-19
**Database Version**: MySQL 5.7+
