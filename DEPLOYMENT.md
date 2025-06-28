# 🚀 Deployment Guide for ytFetch

## Production Deployment on Streamlit Cloud

### Handling YouTube Bot Detection in Production

YouTube aggressively blocks requests from cloud server IPs. To ensure reliable operation in production environments like Streamlit Cloud, follow these strategies:

### Option 1: Cookie Authentication (Recommended for Production)

1. **Export YouTube Cookies from Your Browser**
   
   Using browser extensions:
   - Chrome/Edge: [Get cookies.txt LOCALLY](https://chrome.google.com/webstore/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)
   - Firefox: [cookies.txt](https://addons.mozilla.org/en-US/firefox/addon/cookies-txt/)

2. **Prepare the Cookie File**
   - Sign into YouTube in your browser
   - Export cookies using the extension
   - Save as `cookies.txt` in Netscape format

3. **Deploy with Streamlit Cloud**
   - Add `cookies.txt` to your repository root
   - The app will automatically detect and use the cookie file
   - **Security Note**: Use a secondary YouTube account for cookies

4. **Alternative: Streamlit Secrets**
   ```toml
   # .streamlit/secrets.toml
   [youtube]
   cookie_content = """
   # Netscape HTTP Cookie File
   .youtube.com    TRUE    /    TRUE    1234567890    cookie_name    cookie_value
   ...
   """
   ```

### Option 2: Using a Proxy Service

For higher reliability, consider using a residential proxy service:

1. **Webshare Integration** (Already implemented)
   ```yaml
   # config.yaml
   webshare_username: "your_username"
   webshare_password: "your_password"
   ```

2. **Other Proxy Services**
   - Bright Data (formerly Luminati)
   - SmartProxy
   - Oxylabs

### Option 3: Self-Hosted Solution

Deploy on a residential IP or VPS with good reputation:
- DigitalOcean
- Linode
- AWS EC2 with Elastic IP
- Home server with dynamic DNS

### Fallback Strategy Order (Production)

The enhanced download function tries strategies in this order:
1. Cookie authentication (if `cookies.txt` exists)
2. iOS client simulation with cookies
3. TV embedded client with cookies
4. pytube library (rarely works in production)
5. Web embedded client with cookies
6. MoviePy extraction (backup)

### Monitoring and Maintenance

1. **Cookie Refresh**
   - YouTube cookies expire after ~2 months
   - Set calendar reminder to refresh cookies
   - Monitor download success rate

2. **Error Tracking**
   - Check Streamlit Cloud logs regularly
   - Monitor for "403 Forbidden" errors
   - Update strategies if YouTube changes detection

3. **Backup Methods**
   - Keep multiple cookie files from different accounts
   - Maintain proxy service subscription
   - Have manual download procedure documented

### Environment Variables for Streamlit Cloud

Set these in your Streamlit Cloud dashboard:
```bash
# Optional proxy settings
WEBSHARE_USERNAME=your_username
WEBSHARE_PASSWORD=your_password

# Optional API keys (if not in config.yaml)
GROQ_API_KEY=your_key
OPENAI_API_KEY=your_key
```

### Testing Production Deployment

1. **Local Testing with Production Config**
   ```bash
   # Test with cookie file
   cp cookies.txt.example cookies.txt
   streamlit run appStreamlit.py
   ```

2. **Gradual Rollout**
   - Test with a few videos first
   - Monitor success rate
   - Adjust strategies based on results

### Troubleshooting Common Issues

| Error | Cause | Solution |
|-------|-------|----------|
| HTTP 403 Forbidden | IP blocked | Use cookies or proxy |
| "Sign in to confirm" | Bot detection | Update cookie file |
| All strategies fail | Outdated yt-dlp | Update dependencies |
| Slow downloads | Server throttling | Use proxy service |

### Security Best Practices

1. **Cookie Security**
   - Never use your main YouTube account
   - Rotate cookies regularly
   - Don't commit sensitive cookies to public repos

2. **API Key Management**
   - Use Streamlit secrets for API keys
   - Rotate keys periodically
   - Monitor usage for anomalies

3. **Access Control**
   - Consider adding authentication to your app
   - Rate limit requests
   - Log usage for auditing

### Performance Optimization

1. **Caching**
   - Cache successful downloads
   - Store transcripts in database
   - Implement request deduplication

2. **Resource Management**
   - Clean up temporary files
   - Limit concurrent downloads
   - Monitor memory usage

### Recommended Production Setup

```yaml
# Optimal configuration for Streamlit Cloud
strategies:
  - cookie_auth: true
  - webshare_proxy: true
  - fallback_count: 6
  
performance:
  - max_concurrent: 3
  - cleanup_interval: 3600
  - cache_duration: 86400
```

## Support

For production deployment issues:
- Check [GitHub Issues](https://github.com/lliWcWill/ytFetch/issues)
- Review Streamlit Cloud logs
- Test locally with production config first