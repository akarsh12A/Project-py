import concurrent.futures
import requests
import uuid
import time
import sys

BASE_URL = "http://127.0.0.1:5000/api"

# STEP 5: TEST SINGLE REQUEST FIRST
def test_single_request():
    print(f"--- STEP 5: Testing Single API Connection to {BASE_URL}/orders ---")
    unique_key = str(uuid.uuid4())
    payload = {
        "items": [
            {"item_name": "pizza", "qty": 1}
        ],
        "total_amount": 299.00,
        "currency": "INR",
        "user_id": 999
    }
    headers = {
        "Content-Type": "application/json",
        "Idempotency-Key": unique_key
    }
    
    try:
        response = requests.post(f"{BASE_URL}/orders", json=payload, headers=headers)
        if response.status_code == 200:
            print("SUCCESS: Single Request passed! DB Insertion works.")
            print("Endpoint returned:", response.json())
        else:
            print(f"FAILURE: Cannot proceed to concurrency test. Single request failed.")
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text}")
            sys.exit(1)
    except Exception as e:
        print(f"CRITICAL FAILURE: Could not connect to the Backend API. Is 'python run.py' running aggressively?")
        print(f"Error Details: {str(e)}")
        sys.exit(1)


def place_order(thread_id):
    unique_key = str(uuid.uuid4())
    payload = {
        "items": [
            {"item_name": "pizza", "qty": 1}
        ],
        "total_amount": 299.00,
        "currency": "INR",
        "user_id": thread_id
    }
    headers = {
        "Idempotency-Key": unique_key,
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(f"{BASE_URL}/orders", json=payload, headers=headers)
        
        # STEP 1: PRINT ACTUAL API ERROR natively
        if response.status_code != 200:
            return {"error": f"HTTP {response.status_code} | Body: {response.text}"}
            
        return response.json()
    except Exception as e:
        return {"error": f"Connection/Execution Exception: {str(e)}"}

def run_concurrency_test():
    total_requests = 20
    print(f"\n--- Initiating Concurrency Test => {total_requests} Requests ---")

    start_time = time.time()
    results = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=total_requests) as executor:
        futures = {executor.submit(place_order, i): i for i in range(total_requests)}
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            results.append(res)
            
            # STEP 1: Explicitly print failing error structures
            if "error" in res:
                print(f"API Error Detected: {res['error']}")
            else:
                print(f"Submitted Order: {res.get('order_id', 'ERROR')}")
    
    print(f"\n--- Finished Firing APIs in {round(time.time() - start_time, 2)}s ---")
    print("Wait 5 seconds for Celery workers to finish background inventory threads...\n")
    time.sleep(5)

    print("--- Polling Status via DB endpoints ---")
    success_count = 0
    fail_count = 0
    pending_count = 0
    
    for r in results:
        order_id = r.get("order_id")
        if not order_id:
            continue
            
        try:
            r2 = requests.get(f"{BASE_URL}/orders/{order_id}")
            if r2.status_code == 200:
                final_status = r2.json()
                if final_status.get("status") == "SUCCESS":
                    success_count += 1
                elif final_status.get("status") == "FAILED":
                    fail_count += 1
                else:
                    pending_count += 1
        except Exception as e:
            pass

    print("\n========= CONCURRENCY TEST RESULTS =========")
    print(f"Total Unique Requests Dispatched: {total_requests}")
    print(f"Requests successfully reserving stock (SUCCESS): {success_count}")
    print(f"Requests gracefully denying stock (FAILED): {fail_count}")
    print(f"Requests still processing natively in Celery/DB: {pending_count}")
    print(f"Errors blocking request initially: {len([r for r in results if 'error' in r])}")

if __name__ == "__main__":
    # Always enforce the Single Component Check first
    test_single_request()
    run_concurrency_test()
