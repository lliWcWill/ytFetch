"""
Usage tracking service for ytFetch treasury system.
Handles atomic usage increment and tracking for tier limits.
"""

import logging
from typing import Dict, Any, Optional, List, Literal
from datetime import datetime
from enum import Enum

from ..core.supabase import SupabaseClient, SupabaseError
from ..core.config import get_settings

# Configure logging
logger = logging.getLogger(__name__)

# Usage counter types
class UsageCounter(str, Enum):
    """Types of usage counters we track."""
    JOBS_CREATED = "jobs_created"
    VIDEOS_PROCESSED = "videos_processed"
    TRANSCRIPTION_MINUTES = "transcription_minutes"
    API_CALLS = "api_calls"
    STORAGE_MB = "storage_mb"


class UsageService:
    """
    Service for tracking and managing user usage.
    
    Uses PostgreSQL atomic operations for now, with Redis support
    planned for the future for better performance at scale.
    """
    
    def __init__(self):
        """Initialize the usage service."""
        self.settings = get_settings()
        self._supabase = None
    
    @property
    def supabase(self):
        """Lazy load Supabase client."""
        if self._supabase is None:
            self._supabase = SupabaseClient.get_service_client()
        return self._supabase
    
    async def increment_usage(
        self,
        user_id: str,
        counter_type: UsageCounter,
        increment: int = 1
    ) -> Dict[str, Any]:
        """
        Atomically increment a usage counter for a user.
        
        This uses the PostgreSQL function to ensure atomic updates
        even under high concurrency.
        
        Args:
            user_id: User ID to increment usage for
            counter_type: Type of counter to increment
            increment: Amount to increment by (default 1)
            
        Returns:
            Updated usage data
            
        Raises:
            SupabaseError: If the increment fails
        """
        try:
            # Call the database function for atomic increment
            response = self.supabase.rpc(
                'increment_usage_counter',
                {
                    'p_user_id': user_id,
                    'p_counter_type': counter_type.value,
                    'p_increment': increment
                }
            ).execute()
            
            if not response.data:
                raise SupabaseError(f"Failed to increment usage for user {user_id}")
            
            logger.info(f"Incremented {counter_type.value} by {increment} for user {user_id}")
            return response.data
            
        except Exception as e:
            logger.error(f"Failed to increment usage for user {user_id}: {e}")
            raise SupabaseError(f"Usage increment failed: {str(e)}")
    
    async def get_user_usage(
        self,
        user_id: str,
        period: Literal["daily", "monthly", "all_time"] = "monthly"
    ) -> Dict[str, int]:
        """
        Get user's usage statistics for a specific period.
        
        Args:
            user_id: User ID to get usage for
            period: Time period to get usage for
            
        Returns:
            Dictionary of usage counters and their values
        """
        try:
            # Call the database function to get usage
            response = self.supabase.rpc(
                'get_user_usage',
                {
                    'p_user_id': user_id,
                    'p_period': period
                }
            ).execute()
            
            if not response.data:
                return {}
            
            # Convert the response to a simple dict
            usage_dict = {}
            for row in response.data:
                usage_dict[row['counter_type']] = row['usage_count']
            
            return usage_dict
            
        except Exception as e:
            logger.error(f"Failed to get usage for user {user_id}: {e}")
            return {}
    
    async def get_user_profile_with_usage(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user profile with current usage data.
        
        Args:
            user_id: User ID to get profile for
            
        Returns:
            User profile with usage data or None if not found
        """
        try:
            response = self.supabase.table('user_profiles').select("*").eq('id', user_id).single().execute()
            
            if not response.data:
                return None
            
            profile = response.data
            
            # Extract current month usage
            current_month = datetime.now().strftime("%Y-%m")
            usage_data = profile.get("usage_data", {})
            monthly_usage = usage_data.get("monthly", {}).get(current_month, {})
            all_time_usage = usage_data.get("all_time", {})
            
            # Add formatted usage to profile
            profile['current_usage'] = {
                'monthly': monthly_usage,
                'all_time': all_time_usage
            }
            
            return profile
            
        except Exception as e:
            logger.error(f"Failed to get profile for user {user_id}: {e}")
            return None
    
    async def reset_monthly_usage(self, user_id: str) -> bool:
        """
        Reset monthly usage counters for a user.
        
        This is typically called by a scheduled job at the start of each month
        or when a subscription renews.
        
        Args:
            user_id: User ID to reset usage for
            
        Returns:
            True if successful, False otherwise
        """
        try:
            current_month = datetime.now().strftime("%Y-%m")
            
            # Update the user profile to clear current month's usage
            response = self.supabase.table('user_profiles').update({
                'usage_data': self.supabase.rpc('jsonb_set', {
                    'target': self.supabase.rpc('jsonb_set', {
                        'target': 'usage_data',
                        'path': ['monthly', current_month],
                        'new_value': '{}'
                    }),
                    'path': ['last_reset'],
                    'new_value': f'"{datetime.utcnow().isoformat()}"'
                }),
                'updated_at': datetime.utcnow().isoformat()
            }).eq('id', user_id).execute()
            
            if response.data:
                logger.info(f"Reset monthly usage for user {user_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to reset monthly usage for user {user_id}: {e}")
            return False
    
    async def get_usage_summary(self, user_id: str) -> Dict[str, Any]:
        """
        Get a comprehensive usage summary for a user.
        
        Args:
            user_id: User ID to get summary for
            
        Returns:
            Dictionary with usage summary including limits and remaining quota
        """
        try:
            # Get user profile with usage
            profile = await self.get_user_profile_with_usage(user_id)
            
            if not profile:
                return {
                    "error": "User profile not found",
                    "user_id": user_id
                }
            
            # Get tier limits
            from ..core.auth import TIER_LIMITS
            tier_name = profile.get('tier', 'free')
            tier_limits = TIER_LIMITS.get(tier_name, TIER_LIMITS['free'])
            
            # Get current usage
            current_month = datetime.now().strftime("%Y-%m")
            usage_data = profile.get("usage_data", {})
            monthly_usage = usage_data.get("monthly", {}).get(current_month, {})
            
            # Calculate remaining quota
            summary = {
                "user_id": user_id,
                "tier": tier_name,
                "tier_display_name": tier_limits['display_name'],
                "current_month": current_month,
                "usage": {
                    "jobs_created": {
                        "used": monthly_usage.get("jobs_created", 0),
                        "limit": tier_limits['jobs_per_month'],
                        "remaining": max(0, tier_limits['jobs_per_month'] - monthly_usage.get("jobs_created", 0))
                    },
                    "videos_processed": {
                        "used": monthly_usage.get("videos_processed", 0),
                        "limit": tier_limits['videos_per_month'],
                        "remaining": max(0, tier_limits['videos_per_month'] - monthly_usage.get("videos_processed", 0))
                    },
                    "transcription_minutes": {
                        "used": monthly_usage.get("transcription_minutes", 0),
                        "limit": tier_limits['transcription_minutes_per_month'],
                        "remaining": max(0, tier_limits['transcription_minutes_per_month'] - monthly_usage.get("transcription_minutes", 0))
                    }
                },
                "limits": {
                    "videos_per_job": tier_limits['videos_per_job'],
                    "concurrent_jobs": tier_limits['concurrent_jobs']
                },
                "all_time_stats": usage_data.get("all_time", {}),
                "last_activity": profile.get("last_activity_at"),
                "subscription": {
                    "status": profile.get("stripe_subscription_status"),
                    "ends_at": profile.get("subscription_ends_at")
                }
            }
            
            return summary
            
        except Exception as e:
            logger.error(f"Failed to get usage summary for user {user_id}: {e}")
            return {
                "error": "Failed to get usage summary",
                "user_id": user_id,
                "details": str(e)
            }
    
    async def bulk_increment_usage(
        self,
        user_id: str,
        counters: Dict[UsageCounter, int]
    ) -> Dict[str, Any]:
        """
        Increment multiple usage counters at once.
        
        Args:
            user_id: User ID to increment usage for
            counters: Dictionary of counter types and increment amounts
            
        Returns:
            Updated usage data
        """
        try:
            # For now, we'll do individual increments
            # In the future, this could be optimized with a single database call
            result = None
            for counter_type, increment in counters.items():
                result = await self.increment_usage(user_id, counter_type, increment)
            
            return result or {}
            
        except Exception as e:
            logger.error(f"Failed to bulk increment usage for user {user_id}: {e}")
            raise SupabaseError(f"Bulk usage increment failed: {str(e)}")


# Global instance
usage_service = UsageService()