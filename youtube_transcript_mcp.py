"""
# YouTube Transcript MCP Server

Simple MCP server for fetching transcripts from YouTube videos using the youtube-transcript-api package.

## Features

- `get_transcript`: Get the raw transcript data with timing information
- `get_transcript_text`: Get formatted text transcript (with optional timestamps)
- `list_available_transcripts`: Get all available language options for a video

### Usage Examples

```python
# Get plain text transcript (default)
transcript = await mcp.get_transcript_text(url="https://www.youtube.com/watch?v=dQw4w9WgXcQ")

# Get transcript with timestamps
transcript = await mcp.get_transcript_text(
    url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    include_timestamps=True
)

# Get transcript with raw data included
transcript = await mcp.get_transcript_text(
    url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    include_raw_data=True
)
```

## Claude Configuration

Sample configuration below:

```json
{
  "mcpServers": {
    "youtube-transcript": {
      "command": "/Users/Joshua/.local/bin/uv",
      "args": [
        "run",
        "--with",
        "fastmcp",
        "--with",
        "youtube-transcript-api",
        "--with",
        "pydantic",
        "/Users/Joshua/Documents/_programming/simple-mcp-servers/youtube_transcript_mcp.py"
      ]
    },
    "other servers here": {}
  }
}
```

## Installation

Make sure to install the required packages:
- fastmcp
- youtube-transcript-api
- pydantic

You can install these with pip or your preferred package manager.
"""

import sys
import re
from typing import Dict, Any, List, Optional
from fastmcp import FastMCP
from pydantic import Field
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import JSONFormatter

# Create server
mcp = FastMCP("youtube-transcript")

# Regular expression for extracting video ID from YouTube URLs
YOUTUBE_ID_REGEX = r"(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})"

@mcp.tool()
def get_transcript(
    url: str = Field(description="YouTube video URL or ID"),
    language: str = Field(default="en", description="Language code for transcript (e.g., 'en', 'es', 'fr')")
) -> Dict[str, Any]:
    """
    Fetch the transcript of a YouTube video.
    
    Args:
        url: YouTube video URL or video ID
        language: Language code for the transcript (default: 'en')
        
    Returns:
        Dictionary containing the transcript info and content
    """
    # Log the request to stderr
    print(f"[DEBUG] Processing URL: {url} with language: {language}", file=sys.stderr)
    
    result = {
        "original_url": url,
        "video_id": None,
        "language": language,
        "transcript": None,
        "error": None,
        "available_languages": []
    }
    
    # Extract video ID if URL is provided
    if "youtube.com" in url or "youtu.be" in url:
        video_id_match = re.search(YOUTUBE_ID_REGEX, url)
        if video_id_match:
            result["video_id"] = video_id_match.group(1)
        else:
            result["error"] = "Failed to extract video ID from URL"
            return result
    else:
        # Assume the input is already a video ID
        if len(url) == 11:  # YouTube IDs are 11 characters
            result["video_id"] = url
        else:
            result["error"] = "Invalid YouTube URL or video ID"
            return result
    
    try:
        # Try to get transcript in the requested language
        print(f"[DEBUG] Fetching transcript for video ID: {result['video_id']}", file=sys.stderr)
        
        try:
            # First get available transcript list
            transcript_list = YouTubeTranscriptApi.list_transcripts(result["video_id"])
            
            # Store available languages
            for transcript in transcript_list:
                result["available_languages"].append({
                    "language": transcript.language,
                    "language_code": transcript.language_code,
                    "is_generated": transcript.is_generated
                })
                
            # Get the requested transcript
            transcript = transcript_list.find_transcript([language])
            transcript_data = transcript.fetch()
            
            # Add transcript info
            result["transcript"] = transcript_data
            result["language"] = transcript.language
            result["language_code"] = transcript.language_code
            result["is_generated"] = transcript.is_generated
            
        except Exception as e:
            # If specified language not found, try English or any available transcript
            print(f"[DEBUG] Error with language '{language}', trying fallback: {str(e)}", file=sys.stderr)
            
            try:
                transcript_data = YouTubeTranscriptApi.get_transcript(result["video_id"])
                result["transcript"] = transcript_data
                result["error"] = f"Transcript not available in '{language}', returned default transcript instead"
            except Exception as inner_e:
                result["error"] = f"Failed to get transcript: {str(inner_e)}"
                
    except Exception as e:
        result["error"] = f"Error: {str(e)}"
        
    return result

@mcp.tool()
def get_transcript_text(
    url: str = Field(description="YouTube video URL or ID"),
    language: str = Field(default="en", description="Language code for transcript (e.g., 'en', 'es', 'fr')"),
    include_timestamps: bool = Field(default=False, description="Include timestamps in the formatted text"),
    include_raw_data: bool = Field(default=False, description="Include raw transcript data in the response")
) -> Dict[str, Any]:
    """
    Fetch the transcript of a YouTube video and return it as formatted text.
    
    Args:
        url: YouTube video URL or video ID
        language: Language code for the transcript (default: 'en')
        include_timestamps: Whether to include timestamps in the text
        include_raw_data: Whether to include the raw transcript data in the response
        
    Returns:
        Dictionary containing the transcript as formatted text
    """
    # Get the raw transcript
    raw_result = get_transcript(url, language)
    
    # Create a cleaner result object
    result = {
        "original_url": raw_result["original_url"],
        "video_id": raw_result["video_id"],
        "language": raw_result.get("language"),
        "language_code": raw_result.get("language_code"),
        "error": raw_result["error"]
    }
    
    # If there was an error and no transcript, return early
    if result["error"] and not raw_result["transcript"]:
        return result
    
    # Format the transcript as text
    if raw_result["transcript"]:
        formatted_text = ""
        for item in raw_result["transcript"]:
            if include_timestamps:
                # Convert timestamp to minutes and seconds
                minutes = int(item["start"] // 60)
                seconds = int(item["start"] % 60)
                # Format as [MM:SS]
                formatted_text += f"[{minutes}:{seconds:02d}] {item['text']}\n"
            else:
                formatted_text += f"{item['text']}\n"
        
        result["formatted_text"] = formatted_text
        
        # Optionally include raw transcript data
        if include_raw_data:
            result["transcript"] = raw_result["transcript"]
            result["available_languages"] = raw_result["available_languages"]
    
    return result

@mcp.tool()
def list_available_transcripts(
    url: str = Field(description="YouTube video URL or ID")
) -> Dict[str, Any]:
    """
    List all available transcripts for a YouTube video.
    
    Args:
        url: YouTube video URL or video ID
        
    Returns:
        Dictionary containing the list of available transcripts
    """
    # Extract video ID
    result = {
        "original_url": url,
        "video_id": None,
        "available_languages": [],
        "error": None
    }
    
    # Extract video ID if URL is provided
    if "youtube.com" in url or "youtu.be" in url:
        video_id_match = re.search(YOUTUBE_ID_REGEX, url)
        if video_id_match:
            result["video_id"] = video_id_match.group(1)
        else:
            result["error"] = "Failed to extract video ID from URL"
            return result
    else:
        # Assume the input is already a video ID
        if len(url) == 11:  # YouTube IDs are 11 characters
            result["video_id"] = url
        else:
            result["error"] = "Invalid YouTube URL or video ID"
            return result
    
    try:
        # Get transcript list
        transcript_list = YouTubeTranscriptApi.list_transcripts(result["video_id"])
        
        # Store available languages
        for transcript in transcript_list:
            result["available_languages"].append({
                "language": transcript.language,
                "language_code": transcript.language_code,
                "is_generated": transcript.is_generated
            })
            
    except Exception as e:
        result["error"] = f"Error: {str(e)}"
        
    return result

# Run the server
if __name__ == "__main__":
    mcp.run()
