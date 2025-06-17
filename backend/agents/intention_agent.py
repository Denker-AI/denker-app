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

CRITICAL JSON REQUIREMENTS:
- Response MUST be valid JSON with proper syntax
- Include EXACTLY 3 options, each with different actions
- Use string IDs "1", "2", "3" (in quotes)
- Each option MUST have "id", "title", and "description" fields
- All strings MUST be properly quoted with double quotes
- All commas MUST be present between array elements and object properties
- NO trailing commas allowed
- NO text before or after the JSON object
- Ensure all JSON brackets and braces are properly closed
- Short actionable titles with key context
- Complete context in descriptions"""
    
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
            
            # Try multiple JSON parsing strategies
            data = None
            parsing_errors = []
            
            # Strategy 1: Direct parsing
            try:
                data = json.loads(json_str)
            except json.JSONDecodeError as e:
                parsing_errors.append(f"Direct parsing failed: {e}")
                
                # Strategy 2: Try to fix common JSON issues
                try:
                    # Fix common issues: missing commas, trailing commas, etc.
                    fixed_json = self._fix_common_json_issues(json_str)
                    self.logger.debug(f"Trying fixed JSON: {fixed_json}")
                    data = json.loads(fixed_json)
                except json.JSONDecodeError as e2:
                    parsing_errors.append(f"Fixed JSON parsing failed: {e2}")
                    
                    # Strategy 3: Extract structured data manually if possible
                    try:
                        data = self._extract_options_manually(json_str)
                        if data:
                            self.logger.info("Successfully extracted options manually")
                    except Exception as e3:
                        parsing_errors.append(f"Manual extraction failed: {e3}")
            
            if data is None:
                error_msg = "All JSON parsing strategies failed. Errors: " + "; ".join(parsing_errors)
                self.logger.error(error_msg)
                self.logger.error(f"Original response: {response}")
                # Return default options instead of failing completely
                return self._get_fallback_options(response)
            
            # Validate structure
            if not isinstance(data, dict) or 'options' not in data:
                self.logger.warning("Invalid response structure: missing 'options' key, trying fallback")
                return self._get_fallback_options(response)
            
            options = data['options']
            if not isinstance(options, list):
                self.logger.warning("Invalid response structure: 'options' must be a list, trying fallback")
                return self._get_fallback_options(response)
            
            if len(options) != 3:
                self.logger.warning(f"Invalid number of options: expected 3, got {len(options)}, trying to adjust")
                # Try to adjust the options to exactly 3
                if len(options) > 3:
                    options = options[:3]
                elif len(options) < 3:
                    # Add default options to reach 3
                    while len(options) < 3:
                        options.append({
                            "id": str(len(options) + 1),
                            "title": "General Assistance",
                            "description": "Get help with your current task"
                        })
            
            # Validate and fix each option
            for i, option in enumerate(options, 1):
                if not isinstance(option, dict):
                    self.logger.warning(f"Option {i} is not a dictionary, fixing...")
                    option = {"id": str(i), "title": "General Help", "description": "Get assistance with your task"}
                    options[i-1] = option
                
                # Ensure required fields exist
                if 'id' not in option:
                    option['id'] = str(i)
                if 'title' not in option:
                    option['title'] = "General Help"
                if 'description' not in option:
                    option['description'] = "Get assistance with your current task"
                
                # Fix ID to match expected sequence
                option['id'] = str(i)
            
            return options
            
        except Exception as e:
            self.logger.error(f"Unexpected error parsing options: {str(e)}")
            self.logger.error(f"Response text: {response}")
            self.logger.error(traceback.format_exc())
            # Return fallback options instead of failing
            return self._get_fallback_options(response)

    def _fix_common_json_issues(self, json_str: str) -> str:
        """Try to fix common JSON formatting issues."""
        import re
        
        # Remove any text before the first { and after the last }
        start = json_str.find('{')
        end = json_str.rfind('}') + 1
        if start != -1 and end > start:
            json_str = json_str[start:end]
        
        # Fix missing commas between objects/arrays
        # This is a simple heuristic - look for patterns like }"{ or ]"{ and add commas
        json_str = re.sub(r'}\s*"', '},\n"', json_str)
        json_str = re.sub(r']\s*"', '],\n"', json_str)
        
        # Remove trailing commas before closing brackets
        json_str = re.sub(r',\s*}', '}', json_str)
        json_str = re.sub(r',\s*]', ']', json_str)
        
        return json_str

    def _extract_options_manually(self, json_str: str) -> Optional[Dict]:
        """Try to extract options manually from malformed JSON."""
        import re
        
        # Try to find option patterns manually
        options = []
        
        # Look for id, title, description patterns
        option_pattern = r'"id":\s*"(\d+)".*?"title":\s*"([^"]*)".*?"description":\s*"([^"]*)"'
        matches = re.findall(option_pattern, json_str, re.DOTALL)
        
        for match in matches:
            id_val, title, description = match
            options.append({
                "id": id_val,
                "title": title.strip(),
                "description": description.strip()
            })
        
        if len(options) > 0:
            return {"options": options}
        
        return None

    def _get_fallback_options(self, response: str) -> List[dict]:
        """Return fallback options when JSON parsing fails completely."""
        self.logger.info("Using fallback options due to parsing failure")
        
        # Try to extract any meaningful text from the response for context
        response_preview = response[:200] if response else ""
        
        return [
            {
                "id": "1",
                "title": "Search",
                "description": "Search for information related to your selected content or current context"
            },
            {
                "id": "2", 
                "title": "Explain",
                "description": "Get a detailed explanation of the selected content or what's shown in your screenshot"
            },
            {
                "id": "3",
                "title": "Save", 
                "description": "Save the current content to qdrant database"
            }
        ]
