-- Fix the check_user_limits trigger to handle guest users (NULL user_id)
CREATE OR REPLACE FUNCTION check_user_limits() RETURNS TRIGGER AS $$
DECLARE
  user_tier RECORD;
  job_count INTEGER;
  guest_job_count INTEGER;
  session_id TEXT;
BEGIN
  -- Handle guest users (NULL user_id)
  IF NEW.user_id IS NULL THEN
    -- Extract session_id from metadata
    session_id := NEW.metadata->>'session_id';
    
    -- If no session_id, this is an error
    IF session_id IS NULL THEN
      RAISE EXCEPTION 'Guest users must have a session_id in metadata';
    END IF;
    
    -- Check guest job limit (1 job per session)
    SELECT COUNT(*) INTO guest_job_count
    FROM bulk_jobs
    WHERE user_id IS NULL
      AND metadata->>'session_id' = session_id;
    
    IF guest_job_count >= 1 THEN
      RAISE EXCEPTION 'Guest users can only create 1 bulk job. Please sign in to continue.';
    END IF;
    
    -- Guest users can have up to 60 videos
    IF NEW.total_videos > 60 THEN
      RAISE EXCEPTION 'Guest users can process up to 60 videos per job. Please sign in for higher limits.';
    END IF;
    
    RETURN NEW;
  END IF;
  
  -- For authenticated users, use the existing logic
  -- Get user tier information
  SELECT * INTO user_tier
  FROM user_tiers
  WHERE user_id = NEW.user_id;
  
  -- If no tier record exists, create a free tier
  IF user_tier IS NULL THEN
    INSERT INTO user_tiers (user_id, tier, videos_limit, jobs_per_month, max_concurrent_jobs)
    VALUES (NEW.user_id, 'free', 5, 1, 1);
    
    SELECT * INTO user_tier
    FROM user_tiers
    WHERE user_id = NEW.user_id;
  END IF;
  
  -- Check concurrent job limit
  SELECT COUNT(*) INTO job_count
  FROM bulk_jobs
  WHERE user_id = NEW.user_id
    AND status IN ('pending', 'analyzing', 'processing');
  
  IF job_count >= user_tier.max_concurrent_jobs THEN
    RAISE EXCEPTION 'Concurrent job limit exceeded. Your % tier allows % concurrent jobs.',
      user_tier.tier, user_tier.max_concurrent_jobs;
  END IF;
  
  -- Check video limit for the job
  IF NEW.total_videos > user_tier.videos_limit THEN
    RAISE EXCEPTION 'Video limit exceeded. Your % tier allows % videos per job.',
      user_tier.tier, user_tier.videos_limit;
  END IF;
  
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Recreate the trigger (it will use the updated function)
DROP TRIGGER IF EXISTS check_user_limits_trigger ON bulk_jobs;
CREATE TRIGGER check_user_limits_trigger
  BEFORE INSERT ON bulk_jobs
  FOR EACH ROW
  EXECUTE FUNCTION check_user_limits();