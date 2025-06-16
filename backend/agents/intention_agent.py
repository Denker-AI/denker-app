from typing import Dict, Any, List, Optional
import sys
import base64
from PIL import Image
import io
import os
from datetime import datetime
import time
import json
import traceback
import uuid
import logging

from agents.base_agent import BaseAgent
from config.settings import settings
from services.vertex_ai import vertex_ai_service

logger = logging.getLogger(__name__)

class IntentionAgent(BaseAgent):
    """
    Agent for understanding user intention from screenshot and text
    
    Optimized for:
    - Efficient API calls
    - Error handling and logging
    """
    
    def __init__(self):
        """Initialize the IntentionAgent"""
        self.logger = logging.getLogger(__name__)
        self.logger.info("Initializing IntentionAgent")
        
        # Simple direct logging
        init_message = "🔍 INTENTION AGENT INITIALIZED 🔍"
        print(f"\n\n{init_message}\n\n", flush=True)
        
        # Track performance metrics
        self.metrics = {
            "api_call_time": [],
        }
    
        self.vertex_ai_service = vertex_ai_service
    
    async def process(self, text: Optional[str] = None, screenshot: Optional[str] = None, screenshot_mime_type: Optional[str] = None, mode: str = 'text') -> List[dict]:
        """
        Process user intention based on text and/or screenshot.
        Returns a list of options with id, title, and description.
        """
        try:
            start_time = time.time()
            self.logger.info(f"Processing intention with mode: {mode}")
            
            # Prepare prompt
            prompt_start_time = time.time()
            prompt = self._prepare_prompt(text, screenshot)
            prompt_time = time.time() - prompt_start_time
            self.logger.info(f"Prompt preparation completed in {prompt_time:.2f}s")
            
            # Call Vertex AI with raw screenshot
            self.logger.info("Calling Vertex AI service...")
            vertex_start_time = time.time()
            response = await self.vertex_ai_service.process_multimodal_input(
                text=prompt,
                image_base64=screenshot,  # Pass the raw screenshot
                image_mime_type=screenshot_mime_type, # Pass the mime_type
                max_tokens=300,  # Reduced from 1000 to 300 since we only need ~100-150 tokens
                temperature=0.3
            )
            vertex_time = time.time() - vertex_start_time
            self.logger.info(f"Vertex AI processing completed in {vertex_time:.2f}s")
            
            # Add a check for None or empty response
            if not response:
                self.logger.warning("Received no response from Vertex AI. Returning empty options list.")
                return []

            # Parse response into options
            parse_start_time = time.time()
            options = self._parse_options(response)
            parse_time = time.time() - parse_start_time
            self.logger.info(f"Response parsing completed in {parse_time:.2f}s")
            
            total_time = time.time() - start_time
            self.logger.info(f"Total intention processing completed in {total_time:.2f}s")
            self.logger.info(f"Generated {len(options)} options")
            return options
            
        except Exception as e:
            self.logger.error(f"Error processing intention: {str(e)}")
            self.logger.error(traceback.format_exc())
            raise

    def _prepare_prompt(self, text: Optional[str], screenshot: Optional[str]) -> str:
        """Prepare prompt for Vertex AI based on available inputs."""
        context_description = "Screenshot provided, showing user's current desktop context" if screenshot else "No screenshot provided"
        prompt = f"""Analyze the highlighted text ($content$) and desktop screenshot ($context$). How can you help the user with their current activity and task?

$content$: {text or "(No text selected)"}          
$Context$: {context_description}

1. Analyze $content$:
   - Count words
   - Classify as:
     A: Reference Request (≤4 words, not name/date/place)
     B: Incomplete Sentence (needs completion)
     C: Complete Sentence (needs fact/grammar check, especially for names/dates/places)
     D: LongParagraph (needs summarize/grammar/shorten/add to collection)

2. Extract from $context$:
   - User's current activity and task
   - Key topics/themes
   - User's current using application

3. Generate exactly 3 options in valid JSON format:
{{
    "options": [
        {{
            "id": "1",
            "title": "Short concrete assistance",
            "description": "Detailed explanation and rationale"
        }},
        {{
            "id": "2",
            "title": "Short concrete assistance",
            "description": "Detailed explanation and rationale"
        }},
        {{
            "id": "3",
            "title": "Short concrete assistance",
            "description": "Detailed explanation and rationale"
        }}
    ]
}}

IMPORTANT:
- Response must be valid JSON
- Include exactly 3 options, but have to be three different actions
- Use numbers 1,2,3 as IDs
- Each option must have id, title, and description
- Short actionable titles, not too long but with key context
- Complete context in descriptions
- Do not include any text before or after the JSON"""
    
        return prompt
        
    def _parse_options(self, response: str) -> List[dict]:
        """Parse Vertex AI response into a list of options."""
        try:
            # Clean up the response
            if response is None:
                raise ValueError("Response is None, cannot parse options")
            json_str = response.strip()
            
            # Try to find JSON in the response
            start_idx = json_str.find('{')
            end_idx = json_str.rfind('}') + 1
            if start_idx == -1 or end_idx == 0:
                raise ValueError("No valid JSON found in response")
            
            json_str = json_str[start_idx:end_idx]
            
            # Log the JSON string for debugging
            self.logger.debug(f"Attempting to parse JSON: {json_str}")
            
            # Parse JSON
            data = json.loads(json_str)
            
            # Validate structure
            if not isinstance(data, dict) or 'options' not in data:
                raise ValueError("Invalid response structure: missing 'options' key")
            
            options = data['options']
            if not isinstance(options, list):
                raise ValueError("Invalid response structure: 'options' must be a list")
            
            if len(options) != 3:
                raise ValueError(f"Invalid number of options: expected 3, got {len(options)}")
            
            # Validate each option
            for i, option in enumerate(options, 1):
                if not isinstance(option, dict):
                    raise ValueError(f"Option {i} must be a dictionary")
                if 'id' not in option or 'title' not in option or 'description' not in option:
                    raise ValueError(f"Option {i} missing required fields: id, title, or description")
                if str(option['id']) != str(i):
                    raise ValueError(f"Option {i} has incorrect ID: {option['id']}")
            
            return options
            
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON parsing error: {str(e)}")
            self.logger.error(f"Response text: {response}")
            raise
        except Exception as e:
            self.logger.error(f"Error parsing options: {str(e)}")
            self.logger.error(f"Response text: {response}")
            raise
