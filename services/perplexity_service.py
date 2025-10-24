"""
Perplexity AI service for weather updates and news intelligence
Provides AI-powered insights using Perplexity API
"""

import httpx
import logging
from typing import Dict, Any, Optional
from datetime import datetime
import os

logger = logging.getLogger(__name__)


class PerplexityService:
    """Service for interacting with Perplexity AI API"""
    
    def __init__(self):
        self.api_key = os.getenv("PERPLEXITY_API_KEY", "")
        self.api_url = "https://api.perplexity.ai/chat/completions"
        
        if not self.api_key:
            logger.warning("⚠️ PERPLEXITY_API_KEY not configured. AI features will be disabled.")
        else:
            logger.info("✅ Perplexity AI service initialized")
    
    async def get_weather_forecast(self, site_name: str, location: str, date: str) -> Dict[str, Any]:
        """
        Get hourly weather forecast for a specific site location and date
        
        Args:
            site_name: Name of the site/company
            location: Site location (e.g., "Mumbai, Maharashtra" or "Delhi NCR")
            date: Date for weather forecast (YYYY-MM-DD format)
            
        Returns:
            Dict containing weather forecast with hourly updates
        """
        try:
            if not self.api_key:
                return {
                    "success": False,
                    "error": "Perplexity API not configured",
                    "message": "Please add PERPLEXITY_API_KEY to environment variables"
                }
            
            # Validate date format
            try:
                forecast_date = datetime.strptime(date, "%Y-%m-%d")
                formatted_date = forecast_date.strftime("%B %d, %Y")
            except ValueError:
                return {
                    "success": False,
                    "error": "Invalid date format",
                    "message": "Date must be in YYYY-MM-DD format"
                }
            
            # Create prompt for weather forecast
            prompt = f"""Provide a detailed hourly weather forecast for {site_name} located in {location} on {formatted_date}. 

Include the following information:
1. Overview of the day's weather conditions
2. Hourly breakdown (every 2-3 hours) including:
   - Temperature (in Celsius)
   - Feels like temperature
   - Weather conditions (sunny, cloudy, rainy, etc.)
   - Humidity percentage
   - Wind speed and direction
   - Precipitation probability
   - UV index
3. Sunrise and sunset times
4. Any weather alerts or warnings
5. Recommendations for outdoor activities

Format the response in a clear, structured manner suitable for security personnel planning patrol routes."""

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": "sonar-pro",
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a weather forecasting assistant providing detailed, accurate weather information for security operations planning."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.2,
                "max_tokens": 2000
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(self.api_url, headers=headers, json=payload)
                
                if response.status_code == 200:
                    data = response.json()
                    weather_info = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    
                    return {
                        "success": True,
                        "site_name": site_name,
                        "location": location,
                        "date": date,
                        "formatted_date": formatted_date,
                        "forecast": weather_info,
                        "generated_at": datetime.utcnow().isoformat()
                    }
                else:
                    logger.error(f"Perplexity API error: {response.status_code} - {response.text}")
                    return {
                        "success": False,
                        "error": "API request failed",
                        "message": f"Status code: {response.status_code}"
                    }
                    
        except Exception as e:
            logger.error(f"Failed to get weather forecast: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to fetch weather forecast"
            }
    
    async def get_site_news_intelligence(self, site_name: str, location: str) -> Dict[str, Any]:
        """
        Get comprehensive news and social intelligence about a specific site/company at a location
        
        Args:
            site_name: Name of the company/site (e.g., "Reliance Industries", "TCS Office")
            location: Location/city (e.g., "Mumbai", "Bangalore")
            
        Returns:
            Dict containing news intelligence, social buzz, and analysis
        """
        try:
            if not self.api_key:
                return {
                    "success": False,
                    "error": "Perplexity API not configured",
                    "message": "Please add PERPLEXITY_API_KEY to environment variables"
                }
            
            # Create prompt for site intelligence
            prompt = f"""Provide comprehensive intelligence about {site_name} in {location}. 

Include the following information:

1. **Recent News & Updates** (Last 7 days):
   - Major news articles and announcements
   - Business developments
   - Any incidents or events
   - Media coverage highlights

2. **Social Media Buzz**:
   - Public sentiment and reactions
   - Trending topics related to the site
   - Community discussions
   - Notable social media mentions

3. **Local Impact**:
   - Community relations
   - Local news coverage
   - Public perception
   - Any local concerns or praises

4. **Security & Safety Considerations**:
   - Any reported security incidents
   - Safety concerns or improvements
   - Public gatherings or protests
   - Access restrictions or changes

5. **Business & Operations**:
   - Operational status
   - Employee-related news
   - Visitor information
   - Recent changes or announcements

Provide factual, verified information from credible sources. Focus on recent developments that would be relevant for security management and operational awareness."""

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": "sonar-pro",
                "messages": [
                    {
                        "role": "system",
                        "content": "You are an intelligence analyst providing comprehensive site and location intelligence for security operations. Focus on verified, factual information from credible sources."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.2,
                "max_tokens": 3000
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(self.api_url, headers=headers, json=payload)
                
                if response.status_code == 200:
                    data = response.json()
                    intelligence = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    
                    return {
                        "success": True,
                        "site_name": site_name,
                        "location": location,
                        "intelligence": intelligence,
                        "generated_at": datetime.utcnow().isoformat(),
                        "sources_note": "Information compiled from news sources, social media, and public records"
                    }
                else:
                    logger.error(f"Perplexity API error: {response.status_code} - {response.text}")
                    return {
                        "success": False,
                        "error": "API request failed",
                        "message": f"Status code: {response.status_code}"
                    }
                    
        except Exception as e:
            logger.error(f"Failed to get site intelligence: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to fetch site intelligence"
            }


# Global Perplexity service instance
perplexity_service = PerplexityService()
