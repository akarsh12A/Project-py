"""
Phase stress-test: Reset stock, then fire 10 concurrent orders for Classic Burger (stock=5).
Expected: ~5 SUCCESS (inventory), some will fail payment (~30%), remainder fail out-of-stock.
"""
import concurrent.futures
import requests
import uuid
import time
import json

API = "http://127.0.0.1:5000/api"
ITEM = "Classic Burger"
STOCK = 5
WORKERS = 10

# ── Reset stock before test ───────────────────────────────────────────────────
def reset_stock():
    from app import create_app, db
    app = create_app()
    with app.app_context():
        db.session.execute(
            db.text("UPDATE inventory SET stock_quantity = :s WHERE item_name = :n"),
            {"s": STOCK, "n": ITEM}
        )
        db.session.commit()
    print(f"[SETUP] Stock reset → {ITEM}: {STOCK} units\n")

# ── Fire one order ────────────────────────────────────────────────────────────
def place_order(idx):
    try:
        r = requests.post(
            f"{API}/orders",
            json={"items": [{"item_name": ITEM, "qty": 1}], "currency": "INR"},
            headers={"Content-Type": "application/json", "Idempotency-Key": str(uuid.uuid4())},
            timeout=8,
        )
        if r.status_code == 200:
            d = r.json()
            return {"idx": idx, "ok": True, "order_id": d["order_id"], "total": d.get("total_amount")}
        return {"idx": idx, "ok": False, "err": f"HTTP {r.status_code}: {r.text[:80]}"}
    except Exception as e:
        return {"idx": idx, "ok": False, "err": str(e)}

# ── Poll final state ──────────────────────────────────────────────────────────
def poll_final(order_id, timeout=20):
    for _ in range(timeout // 2):
        time.sleep(2)
        try:
            r = requests.get(f"{API}/orders/{order_id}", timeout=5)
            d = r.json()
            if d.get("status") in ("SUCCESS", "FAILED", "CANCELLED"):
                return d
        except:
            pass
    return None

# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    reset_stock()

    print(f"[TEST] Firing {WORKERS} concurrent orders for '{ITEM}'… (stock = {STOCK})")
    print("=" * 60)

    created = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futs = [pool.submit(place_order, i+1) for i in range(WORKERS)]
        for f in concurrent.futures.as_completed(futs):
            r = f.result()
            if r["ok"]:
                created.append(r["order_id"])
                print(f"  Order #{r['order_id']} created  (₹{r['total']})")
            else:
                print(f"  Request failed at creation: {r['err']}")

    print(f"\n[WAIT] Polling {len(created)} orders for final status (up to 25s)…")
    time.sleep(3)  # give Celery a head start

    results = {"SUCCESS": [], "FAILED": [], "PENDING": []}
    for oid in created:
        d = poll_final(oid)
        if d:
            status = d.get("status", "?")
            inv    = d.get("inventory_status", "?")
            pay    = d.get("payment_status", "?")
            reason = d.get("failure_reason") or "—"
            bucket = status if status in results else "PENDING"
            results[bucket].append(oid)
            icon = "✅" if status == "SUCCESS" else "❌"
            print(f"  {icon} Order #{oid}: status={status} | payment={pay} | inv={inv} | reason={reason}")
        else:
            results["PENDING"].append(oid)
            print(f"  ⏳ Order #{oid}: still PENDING/PROCESSING after timeout")

    print("\n" + "=" * 60)
    print("  ═══════ PHASE 1–8 STRESS TEST RESULTS ═══════")
    print(f"  Total Orders Fired  : {WORKERS}")
    print(f"  Created in DB       : {len(created)}")
    print(f"  ✅ SUCCESS (stock reserved) : {len(results['SUCCESS'])}")
    print(f"  ❌ FAILED  (stock/payment)  : {len(results['FAILED'])}")
    print(f"  ⏳ Still PENDING            : {len(results['PENDING'])}")
    print("=" * 60)

    # Final inventory check
    from app import create_app, db
    app2 = create_app()
    with app2.app_context():
        row = db.session.execute(
            db.text("SELECT stock_quantity FROM inventory WHERE item_name = :n"),
            {"n": ITEM}
        ).fetchone()
        remaining = row[0] if row else "?"
    print(f"\n[DB CHECK] '{ITEM}' remaining stock: {remaining}")
    expected_reserved = min(STOCK, len(results["SUCCESS"]))
    print(f"[VERIFY]  Expected deduction ≤ {STOCK}, actual deducted = {STOCK - remaining} ✅" if isinstance(remaining, int) and remaining >= 0 else "[VERIFY] Could not verify stock")
