"""
Grok API Client
Handles communication with xAI's Grok API
"""

import os
import requests
import logging
from typing import List, Dict, Optional, Any

logger = logging.getLogger(__name__)


class GrokClient:
    """Client for interacting with Grok API"""
    
    def __init__(self, api_key: Optional[str] = None, base_url: str = "https://api.x.ai/v1", model: str = "grok-beta"):
        """
        Initialize Grok API client
        
        Args:
            api_key: xAI API key (from env if not provided)
            base_url: API base URL
            model: Model to use (grok-beta, grok-2, etc.)
        """
        self.api_key = api_key or os.getenv("GROK_API_KEY")
        if not self.api_key:
            raise ValueError("GROK_API_KEY not found in environment or provided")
        
        self.base_url = base_url
        self.model = model
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        logger.info(f"Grok client initialized with model: {model}")
    
    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1000,
        stream: bool = False
    ) -> Dict[str, Any]:
        """
        Send a chat completion request to Grok
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens to generate
            stream: Whether to stream the response
        
        Returns:
            API response dict
        """
        url = f"{self.base_url}/chat/completions"
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream
        }
        
        try:
            response = requests.post(url, json=payload, headers=self.headers, timeout=60)
            response.raise_for_status()
            
            result = response.json()
            logger.info(f"Grok API call successful. Tokens used: {result.get('usage', {})}")
            return result
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Grok API error: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response: {e.response.text}")
            raise
    
    def simple_chat(self, user_message: str, system_prompt: Optional[str] = None) -> str:
        """
        Simple chat interface - send a message and get a response
        
        Args:
            user_message: The user's message
            system_prompt: Optional system prompt
        
        Returns:
            Grok's response text
        """
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": user_message})
        
        response = self.chat_completion(messages)
        
        # Extract the assistant's response
        assistant_message = response["choices"][0]["message"]["content"]
        return assistant_message
    
    def chat_with_context(
        self,
        user_message: str,
        conversation_history: List[Dict[str, str]],
        system_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Chat with conversation history context
        
        Args:
            user_message: Current user message
            conversation_history: List of previous messages
            system_prompt: Optional system prompt
        
        Returns:
            Full API response including usage stats
        """
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        # Add conversation history
        messages.extend(conversation_history)
        
        # Add current message
        messages.append({"role": "user", "content": user_message})
        
        response = self.chat_completion(messages)
        return response
    
    def test_connection(self) -> bool:
        """Test if API connection is working"""
        try:
            response = self.simple_chat("Hello! Can you respond with just 'OK'?")
            logger.info("Grok API connection test successful")
            return True
        except Exception as e:
            logger.error(f"Grok API connection test failed: {e}")
            return False


def initialize_grok_client(api_key: Optional[str] = None, model: str = "grok-beta") -> GrokClient:
    """Initialize and return Grok client"""
    try:
        client = GrokClient(api_key=api_key, model=model)
        logger.info("Grok client initialized successfully")
        return client
    except Exception as e:
        logger.error(f"Failed to initialize Grok client: {e}")
        raise
