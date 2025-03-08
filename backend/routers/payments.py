import os
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request
import stripe
from ..models.subscription import SubscriptionDocument
from ..security import verify_api_key
from ..db import get_db

router = APIRouter(prefix="/api/payments", tags=["payments"])

# Initialize Stripe with the secret key
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
STRIPE_PRICE_ID = os.getenv("STRIPE_PRICE_ID")


@router.post("/create-checkout-session")
async def create_checkout_session(request: Request, api_key: str = Depends(verify_api_key)):
    """Create a Stripe checkout session for subscription."""
    body = await request.json()
    user_id = body.get("userId")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID is required")

    db = get_db()

    # Check if user already has an active subscription
    subscription = await db.subscriptions.find_one({"user_id": user_id, "status": "active"})
    if subscription:
        raise HTTPException(status_code=400, detail="User already has an active subscription")

    try:
        # Create or retrieve Stripe customer
        customer = await db.subscriptions.find_one({"user_id": user_id})
        if customer and customer.get("stripe_customer_id"):
            stripe_customer_id = customer["stripe_customer_id"]
        else:
            stripe_customer = stripe.Customer.create(metadata={"user_id": user_id})
            stripe_customer_id = stripe_customer.id

            # Create subscription document
            subscription_doc = SubscriptionDocument(user_id=user_id, stripe_customer_id=stripe_customer_id)
            await db.subscriptions.insert_one(subscription_doc.dict())

        # Create checkout session
        checkout_session = stripe.checkout.Session.create(
            customer=stripe_customer_id,
            payment_method_types=["card"],
            line_items=[
                {
                    "price": STRIPE_PRICE_ID,
                    "quantity": 1,
                }
            ],
            mode="subscription",
            success_url=f"{os.getenv('FRONTEND_URL')}/subscription/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{os.getenv('FRONTEND_URL')}/subscription/cancel",
        )

        return {"sessionId": checkout_session.id}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/webhook")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    db = get_db()

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        customer_id = session["customer"]
        subscription_id = session["subscription"]

        # Update subscription status
        await db.subscriptions.update_one(
            {"stripe_customer_id": customer_id},
            {
                "$set": {
                    "stripe_subscription_id": subscription_id,
                    "status": "active",
                    "current_period_end": datetime.fromtimestamp(session["subscription_end"]),
                    "updated_at": datetime.utcnow(),
                }
            },
        )

    elif event["type"] == "customer.subscription.updated":
        subscription = event["data"]["object"]
        customer_id = subscription["customer"]

        await db.subscriptions.update_one(
            {"stripe_customer_id": customer_id},
            {
                "$set": {
                    "status": subscription["status"],
                    "current_period_end": datetime.fromtimestamp(subscription["current_period_end"]),
                    "updated_at": datetime.utcnow(),
                }
            },
        )

    return {"status": "success"}


@router.get("/subscription-status/{user_id}")
async def get_subscription_status(user_id: str, api_key: str = Depends(verify_api_key)):
    """Get user's subscription status."""
    db = get_db()
    subscription = await db.subscriptions.find_one({"user_id": user_id})

    if not subscription:
        return {"status": "inactive"}

    return {
        "status": subscription["status"],
        "currentPeriodEnd": subscription.get("current_period_end"),
        "stripeCustomerId": subscription["stripe_customer_id"],
        "stripeSubscriptionId": subscription.get("stripe_subscription_id"),
    }
