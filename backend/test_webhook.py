#!/usr/bin/env python3
"""
Test script to manually trigger Stripe webhook for token purchase
"""

import requests
import json
from datetime import datetime

# Test webhook endpoint
WEBHOOK_URL = "http://localhost:8000/api/tokens/webhook/stripe"

# Simulate a Stripe checkout.session.completed event
test_event = {
    "id": "evt_test_webhook",
    "object": "event",
    "api_version": "2023-10-16",
    "created": int(datetime.now().timestamp()),
    "data": {
        "object": {
            "id": "cs_test_manual_123456",
            "object": "checkout.session",
            "amount_total": 699,  # $6.99 in cents
            "currency": "usd",
            "customer": None,
            "customer_email": "test@example.com",
            "metadata": {
                "user_id": "f32e1531-e1a5-429e-92af-b1f2a10d0abb",
                "package_id": "popular",
                "tokens": "250"
            },
            "mode": "payment",
            "payment_intent": "pi_test_123456",
            "payment_status": "paid",
            "status": "complete",
            "success_url": "http://localhost:3000/tokens/success"
        }
    },
    "livemode": False,
    "pending_webhooks": 1,
    "request": {
        "id": None,
        "idempotency_key": None
    },
    "type": "checkout.session.completed"
}

# Send the test webhook
headers = {
    "Content-Type": "application/json",
    "stripe-signature": "test_signature"
}

response = requests.post(WEBHOOK_URL, json=test_event, headers=headers)

print(f"Response Status: {response.status_code}")
print(f"Response Body: {response.json()}")

# Check token balance after webhook
import time
time.sleep(2)  # Wait for processing

print("\nChecking token balance...")
# You can add code here to check the token balance via the API