#!/usr/bin/env python3
"""
Bulk API Demonstration Script

This script demonstrates how to use the new bulk API endpoints for
playlist and channel transcription operations.

Usage:
    python bulk_api_demo.py

Requirements:
    - ytFetch backend server running on localhost:8000
    - Valid YouTube playlist or channel URL for testing
"""

import asyncio
import json
import time
from typing import Dict, Any

import aiohttp


class BulkAPIClient:
    """Client for interacting with ytFetch bulk API endpoints."""
    
    def __init__(self, base_url: str = "http://localhost:8000", user_token: str = None):
        self.base_url = base_url
        self.session = None
        self.headers = {}
        
        if user_token:
            # Format: "user_id:tier" (e.g., "demo_user:pro")
            self.headers["Authorization"] = f"Bearer {user_token}"
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(headers=self.headers)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def analyze_source(self, url: str, max_videos: int = None) -> Dict[str, Any]:
        """Analyze a playlist or channel URL."""
        data = {"url": url}
        if max_videos:
            data["max_videos"] = max_videos
        
        async with self.session.post(f"{self.base_url}/api/v1/bulk/analyze", json=data) as response:
            if response.status != 200:
                error_text = await response.text()
                raise Exception(f"Analysis failed: {response.status} - {error_text}")
            return await response.json()
    
    async def create_bulk_job(
        self, 
        url: str, 
        transcript_method: str = "unofficial",
        output_format: str = "txt",
        max_videos: int = None,
        webhook_url: str = None
    ) -> Dict[str, Any]:
        """Create a new bulk transcription job."""
        data = {
            "url": url,
            "transcript_method": transcript_method,
            "output_format": output_format
        }
        
        if max_videos:
            data["max_videos"] = max_videos
        if webhook_url:
            data["webhook_url"] = webhook_url
        
        async with self.session.post(f"{self.base_url}/api/v1/bulk/create", json=data) as response:
            if response.status != 201:
                error_text = await response.text()
                raise Exception(f"Job creation failed: {response.status} - {error_text}")
            return await response.json()
    
    async def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """Get the status of a bulk job."""
        async with self.session.get(f"{self.base_url}/api/v1/bulk/jobs/{job_id}") as response:
            if response.status != 200:
                error_text = await response.text()
                raise Exception(f"Failed to get job status: {response.status} - {error_text}")
            return await response.json()
    
    async def list_jobs(self, page: int = 1, per_page: int = 20) -> Dict[str, Any]:
        """List user's bulk jobs."""
        params = {"page": page, "per_page": per_page}
        async with self.session.get(f"{self.base_url}/api/v1/bulk/jobs", params=params) as response:
            if response.status != 200:
                error_text = await response.text()
                raise Exception(f"Failed to list jobs: {response.status} - {error_text}")
            return await response.json()
    
    async def start_job(self, job_id: str) -> Dict[str, Any]:
        """Start processing a bulk job."""
        async with self.session.post(f"{self.base_url}/api/v1/bulk/jobs/{job_id}/start") as response:
            if response.status != 202:
                error_text = await response.text()
                raise Exception(f"Failed to start job: {response.status} - {error_text}")
            return await response.json()
    
    async def cancel_job(self, job_id: str) -> Dict[str, Any]:
        """Cancel a bulk job."""
        async with self.session.post(f"{self.base_url}/api/v1/bulk/jobs/{job_id}/cancel") as response:
            if response.status != 200:
                error_text = await response.text()
                raise Exception(f"Failed to cancel job: {response.status} - {error_text}")
            return await response.json()
    
    async def download_results(self, job_id: str, output_file: str = None) -> bytes:
        """Download ZIP file with all transcripts."""
        async with self.session.get(f"{self.base_url}/api/v1/bulk/jobs/{job_id}/download") as response:
            if response.status != 200:
                error_text = await response.text()
                raise Exception(f"Failed to download results: {response.status} - {error_text}")
            
            content = await response.read()
            
            if output_file:
                with open(output_file, 'wb') as f:
                    f.write(content)
                print(f"Results saved to {output_file}")
            
            return content
    
    async def delete_job(self, job_id: str) -> Dict[str, Any]:
        """Delete a bulk job."""
        async with self.session.delete(f"{self.base_url}/api/v1/bulk/jobs/{job_id}") as response:
            if response.status != 200:
                error_text = await response.text()
                raise Exception(f"Failed to delete job: {response.status} - {error_text}")
            return await response.json()


async def demo_bulk_workflow():
    """Demonstrate a complete bulk transcription workflow."""
    
    # Demo configuration
    DEMO_PLAYLIST_URL = "https://www.youtube.com/playlist?list=PLrAXtmRdnEQy6nuLvVeZmrM1Xy2PS9sTG"  # Replace with actual playlist
    USER_TOKEN = "demo_user:pro"  # Simulated user with pro tier
    
    print("🚀 ytFetch Bulk API Demonstration")
    print("=" * 50)
    
    async with BulkAPIClient(user_token=USER_TOKEN) as client:
        try:
            # Step 1: Analyze the source
            print("📊 Step 1: Analyzing playlist/channel...")
            analysis = await client.analyze_source(DEMO_PLAYLIST_URL, max_videos=5)
            
            print(f"✅ Found {analysis['total_videos']} videos")
            print(f"   Source type: {analysis['source_type']}")
            print(f"   Title: {analysis['title']}")
            print(f"   Estimated duration: {analysis['estimated_duration_hours']:.2f} hours")
            print(f"   Can process all: {analysis['can_process_all']}")
            print()
            
            # Step 2: Create bulk job
            print("📝 Step 2: Creating bulk transcription job...")
            job = await client.create_bulk_job(
                url=DEMO_PLAYLIST_URL,
                transcript_method="unofficial",  # Fast method for demo
                output_format="txt",
                max_videos=3  # Limit for demo
            )
            
            job_id = job["job_id"]
            print(f"✅ Created job: {job_id}")
            print(f"   Total videos: {job['total_videos']}")
            print(f"   Status: {job['status']}")
            print(f"   Estimated duration: {job.get('estimated_duration_minutes', 'N/A')} minutes")
            print()
            
            # Step 3: Start job processing
            print("▶️ Step 3: Starting job processing...")
            start_result = await client.start_job(job_id)
            print(f"✅ Job started: {start_result['message']}")
            print()
            
            # Step 4: Monitor job progress
            print("👀 Step 4: Monitoring job progress...")
            max_wait_time = 300  # 5 minutes max
            start_time = time.time()
            
            while time.time() - start_time < max_wait_time:
                status = await client.get_job_status(job_id)
                
                print(f"   Status: {status['status']} | "
                      f"Progress: {status['progress_percent']:.1f}% | "
                      f"Completed: {status['completed_videos']}/{status['total_videos']} | "
                      f"Failed: {status['failed_videos']}")
                
                if status['status'] in ['completed', 'failed', 'cancelled']:
                    break
                
                await asyncio.sleep(10)  # Check every 10 seconds
            
            print()
            
            # Step 5: Check final status and download results
            final_status = await client.get_job_status(job_id)
            
            if final_status['status'] == 'completed' and final_status['zip_available']:
                print("💾 Step 5: Downloading results...")
                output_file = f"bulk_transcripts_{job_id[:8]}.zip"
                await client.download_results(job_id, output_file)
                print(f"✅ Results downloaded to {output_file}")
            else:
                print(f"⚠️ Job finished with status: {final_status['status']}")
                print(f"   Completed: {final_status['completed_videos']} videos")
                print(f"   Failed: {final_status['failed_videos']} videos")
            
            print()
            
            # Step 6: List all jobs
            print("📋 Step 6: Listing user jobs...")
            jobs_list = await client.list_jobs()
            print(f"✅ Found {len(jobs_list['jobs'])} jobs:")
            
            for job_info in jobs_list['jobs'][:3]:  # Show first 3
                print(f"   • {job_info['job_id'][:8]}... | "
                      f"Status: {job_info['status']} | "
                      f"Videos: {job_info['completed_videos']}/{job_info['total_videos']} | "
                      f"Created: {job_info['created_at'][:10]}")
            
            print()
            
            # Optional: Clean up (delete demo job)
            print("🧹 Step 7: Cleaning up...")
            # Uncomment the next line to delete the demo job
            # delete_result = await client.delete_job(job_id)
            # print(f"✅ Job deleted: {delete_result['message']}")
            
        except Exception as e:
            print(f"❌ Error during demo: {e}")
            return False
    
    print("🎉 Bulk API demonstration completed successfully!")
    return True


async def demo_api_endpoints():
    """Demonstrate individual API endpoints."""
    
    print("\n📚 API Endpoints Reference")
    print("=" * 50)
    
    endpoints = [
        ("POST", "/api/v1/bulk/analyze", "Analyze playlist/channel before creating job"),
        ("POST", "/api/v1/bulk/create", "Create a new bulk transcription job"),
        ("GET", "/api/v1/bulk/jobs/{job_id}", "Get status and progress of a specific job"),
        ("GET", "/api/v1/bulk/jobs", "List user's bulk jobs with pagination"),
        ("POST", "/api/v1/bulk/jobs/{job_id}/start", "Start processing a pending job"),
        ("POST", "/api/v1/bulk/jobs/{job_id}/cancel", "Cancel a running or pending job"),
        ("GET", "/api/v1/bulk/jobs/{job_id}/download", "Download ZIP file with all transcripts"),
        ("DELETE", "/api/v1/bulk/jobs/{job_id}", "Delete a job and all its data"),
    ]
    
    for method, endpoint, description in endpoints:
        print(f"{method:6} {endpoint:35} - {description}")
    
    print("\n🔐 Authentication")
    print("- Include 'Authorization: Bearer user_id:tier' header")
    print("- Supported tiers: free, basic, pro, enterprise")
    print("- Example: 'Authorization: Bearer demo_user:pro'")
    
    print("\n⚡ Rate Limits")
    print("- /analyze: 10 requests/minute")
    print("- /create: 5 requests/minute")  
    print("- /start: 3 requests/minute")
    print("- /cancel: 5 requests/minute")
    
    print("\n📊 User Tier Limits")
    tiers = {
        "free": {"max_videos": 5, "max_jobs": 1, "daily_limit": 10},
        "basic": {"max_videos": 25, "max_jobs": 2, "daily_limit": 50},
        "pro": {"max_videos": 100, "max_jobs": 3, "daily_limit": 200},
        "enterprise": {"max_videos": 500, "max_jobs": 5, "daily_limit": 1000}
    }
    
    for tier, limits in tiers.items():
        print(f"- {tier:10}: {limits['max_videos']:3} videos/job, "
              f"{limits['max_jobs']} concurrent jobs, "
              f"{limits['daily_limit']} videos/day")


if __name__ == "__main__":
    print("Choose demo mode:")
    print("1. Full workflow demonstration")
    print("2. API endpoints reference")
    print("3. Both")
    
    choice = input("Enter choice (1-3): ").strip()
    
    async def run_demos():
        if choice in ["1", "3"]:
            success = await demo_bulk_workflow()
            if not success:
                print("⚠️ Workflow demo failed. Make sure the ytFetch backend is running.")
        
        if choice in ["2", "3"]:
            await demo_api_endpoints()
    
    try:
        asyncio.run(run_demos())
    except KeyboardInterrupt:
        print("\n👋 Demo interrupted by user")
    except Exception as e:
        print(f"❌ Demo failed: {e}")
        print("💡 Make sure the ytFetch backend server is running on localhost:8000")