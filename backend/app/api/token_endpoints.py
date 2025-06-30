from fastapi import APIRouter, Depends, HTTPException, Query, Request
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel
import stripe
import logging

from app.core.auth import get_current_user, AuthenticatedUser
from app.core.supabase import get_supabase_anon, get_supabase_service
from app.core.stripe_config import STRIPE_CONFIG

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tokens", tags=["tokens"])

# Stripe API key will be set when needed

# Pydantic models
class TokenBalance(BaseModel):
    userId: str
    balance: int
    lifetimeSpent: int
    lifetimePurchased: int
    lastPurchaseAt: Optional[datetime]
    createdAt: datetime
    updatedAt: datetime

class TokenTransaction(BaseModel):
    id: str
    userId: str
    amount: int
    type: str  # purchase, usage, refund, bonus
    description: str
    metadata: Dict[str, Any]
    createdAt: datetime

class PurchaseTokensRequest(BaseModel):
    package_id: str
    tokens: int
    price: float

class UseTokensRequest(BaseModel):
    job_id: str
    video_count: int = 1
    amount: int

class PurchaseResponse(BaseModel):
    checkout_url: str
    session_id: str

# Token packages configuration
# For testing, use Stripe test price IDs - replace with your actual price IDs from Stripe Dashboard
TOKEN_PACKAGES = {
    "starter": {
        "id": "starter",
        "tokens": 50,
        "price": 2.99,
        "stripe_price_id": "price_1Rf5JGBDd5XvmPbiSFKHjaOE"  # Test price ID - replace with actual
    },
    "popular": {
        "id": "popular",
        "tokens": 250,  # Updated to match frontend
        "price": 6.99,
        "stripe_price_id": "price_1Rf4gpBDd5XvmPbiXDq77Xhq"  # Test price ID - replace with actual
    },
    "volume": {
        "id": "volume",
        "tokens": 1000,  # Updated to match frontend  
        "price": 17.99,
        "stripe_price_id": "price_1Rf5NNBDd5XvmPbisqDUKRq4"  # Test price ID - replace with actual
    }
}

@router.get("/balance", response_model=TokenBalance)
async def get_token_balance(user: AuthenticatedUser = Depends(get_current_user)):
    """Get user's current token balance"""
    try:
        supabase = get_supabase_anon()
        
        # Get or create user balance
        result = supabase.table("user_token_balances") \
            .select("*") \
            .eq("user_id", user.id) \
            .single() \
            .execute()
        
        if not result.data:
            # Create initial balance
            create_result = supabase.table("user_token_balances") \
                .insert({
                    "user_id": user.id,
                    "balance": 0,
                    "lifetime_purchased": 0,
                    "lifetime_spent": 0
                }) \
                .select() \
                .single() \
                .execute()
            
            if not create_result.data:
                # If we still don't have data, return a default response
                return TokenBalance(
                    userId=user.id,
                    balance=0,
                    lifetimeSpent=0,
                    lifetimePurchased=0,
                    lastPurchaseAt=None,
                    createdAt=datetime.now(),
                    updatedAt=datetime.now()
                )
            
            balance_data = create_result.data
        else:
            balance_data = result.data
        
        return TokenBalance(
            userId=balance_data["user_id"],
            balance=balance_data["balance"],
            lifetimeSpent=balance_data["lifetime_spent"],
            lifetimePurchased=balance_data["lifetime_purchased"],
            lastPurchaseAt=balance_data.get("last_purchase_at"),
            createdAt=balance_data["created_at"],
            updatedAt=balance_data["updated_at"]
        )
        
    except Exception as e:
        logger.error(f"Failed to get token balance: {e}")
        # Return a default balance instead of failing
        return TokenBalance(
            userId=user.id,
            balance=0,
            lifetimeSpent=0,
            lifetimePurchased=0,
            lastPurchaseAt=None,
            createdAt=datetime.now(),
            updatedAt=datetime.now()
        )

@router.get("/transactions", response_model=Dict[str, Any])
async def get_transactions(
    user: AuthenticatedUser = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """Get user's transaction history"""
    try:
        supabase = get_supabase_anon()
        
        # Get total count
        count_result = supabase.table("token_transactions") \
            .select("id", count="exact") \
            .eq("user_id", user.id) \
            .execute()
        
        total = count_result.count
        
        # Get transactions
        result = supabase.table("token_transactions") \
            .select("*") \
            .eq("user_id", user.id) \
            .order("created_at", desc=True) \
            .range(offset, offset + limit - 1) \
            .execute()
        
        transactions = [
            TokenTransaction(
                id=t["id"],
                userId=t["user_id"],
                amount=t["amount"],
                type=t["type"],
                description=t["description"],
                metadata=t.get("metadata", {}),
                createdAt=t["created_at"]
            )
            for t in result.data
        ]
        
        return {
            "transactions": transactions,
            "total": total
        }
        
    except Exception as e:
        logger.error(f"Failed to get transactions: {e}")
        raise HTTPException(status_code=500, detail="Failed to get transactions")

@router.post("/purchase", response_model=PurchaseResponse)
async def purchase_tokens(
    purchase_request: PurchaseTokensRequest,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """Create a Stripe checkout session for token purchase"""
    try:
        # Ensure Stripe API key is set
        if not stripe.api_key:
            stripe.api_key = STRIPE_CONFIG["secret_key"]
            
        logger.info(f"Stripe API key configured: {bool(stripe.api_key)}")
        logger.info(f"Creating checkout for package: {purchase_request.package_id}")
            
        package = TOKEN_PACKAGES.get(purchase_request.package_id)
        if not package:
            raise HTTPException(status_code=400, detail="Invalid token package")
        
        # Use the email from the authenticated user object
        user_email = user.email
        
        # Create Stripe checkout session
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            customer_email=user_email,
            line_items=[{
                "price": package["stripe_price_id"],
                "quantity": 1,
            }],
            mode="payment",
            success_url=f"{request.headers.get('origin', 'http://localhost:3000')}/tokens/success?package={purchase_request.package_id}&tokens={package['tokens']}&session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{request.headers.get('origin', 'http://localhost:3000')}/pricing?canceled=true",
            metadata={
                "user_id": user.id,
                "package_id": purchase_request.package_id,
                "tokens": str(package["tokens"])
            }
        )
        
        return PurchaseResponse(
            checkout_url=session.url,
            session_id=session.id
        )
        
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create checkout session: {e}")
        raise HTTPException(status_code=500, detail="Failed to create checkout session")

@router.post("/use")
async def use_tokens(
    request: UseTokensRequest,
    user: AuthenticatedUser = Depends(get_current_user)
):
    """Use tokens for a transcription job"""
    try:
        supabase = get_supabase_anon()
        
        # Call the use_tokens function
        result = supabase.rpc("use_tokens", {
            "p_user_id": user.id,
            "p_amount": request.amount,
            "p_description": f"Transcription job {request.job_id} - {request.video_count} video(s)",
            "p_metadata": {
                "job_id": request.job_id,
                "video_count": request.video_count
            }
        }).execute()
        
        if not result.data:
            raise HTTPException(status_code=400, detail="Insufficient token balance")
        
        balance = result.data
        
        return {
            "success": True,
            "remainingBalance": balance["balance"]
        }
        
    except Exception as e:
        logger.error(f"Failed to use tokens: {e}")
        if "Insufficient token balance" in str(e):
            raise HTTPException(status_code=400, detail="Insufficient token balance")
        raise HTTPException(status_code=500, detail="Failed to use tokens")

@router.post("/webhook/stripe")
async def stripe_webhook(request: dict):
    """Handle Stripe webhook for successful token purchases"""
    # This would be implemented to handle Stripe webhooks
    # For now, we'll handle it in the existing stripe_webhook_handlers
    pass