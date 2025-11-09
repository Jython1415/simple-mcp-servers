#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "fastmcp",
#     "pydantic",
#     "httpx"
# ]
# ///

"""
# Google Maps MCP Server

Simple MCP server for Google Maps integration providing geocoding, place search, directions, and location services.

## Claude Configuration

Sample configuration:

```json
{
  "mcpServers": {
    "google-maps": {
      "command": "/Users/Joshua/.local/bin/uv",
      "args": [
        "run",
        "--script",
        "/Users/Joshua/Documents/_programming/simple-mcp-servers/google_maps_mcp.py"
      ],
      "env": {
        "GOOGLE_MAPS_API_KEY": "{{ GOOGLE_MAPS_API_KEY }}"
      }
    }
  }
}
```

## Claude Code Setup

Add to Claude Code with:
```bash
claude mcp add google-maps /Users/Joshua/Documents/_programming/simple-mcp-servers/google_maps_mcp.py
```

## Features

- **Geocoding**: Convert addresses to coordinates
- **Reverse Geocoding**: Convert coordinates to addresses  
- **Place Search**: Find places by query with location bias
- **Place Details**: Get detailed information about specific places
- **Distance Matrix**: Calculate distances and travel times
- **Directions**: Get turn-by-turn directions between locations
- **Elevation**: Get elevation data for coordinates

## Google Maps API Setup

This server requires a Google Maps API key with the following APIs enabled:
- Google Maps Geocoding API
- Google Maps Places API  
- Google Maps Directions API
- Google Maps Distance Matrix API
- Google Maps Elevation API

Set your API key as the `GOOGLE_MAPS_API_KEY` environment variable.

## History

Created to replace complex Docker-based solutions with a simple, reliable MCP server following
the established pattern from other working servers in this directory.
"""

import os
import sys
from typing import Dict, Any, List, Optional
from fastmcp import FastMCP
from pydantic import Field
import httpx


# Create server
mcp = FastMCP("google-maps")


def get_api_key() -> str:
    """Get Google Maps API key from environment with error handling."""
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not api_key:
        print("Error: GOOGLE_MAPS_API_KEY environment variable is required", file=sys.stderr)
        sys.exit(1)
    return api_key


def make_api_request(url: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Make API request with consistent error handling."""
    result = {
        "success": False,
        "data": None,
        "error": None
    }
    
    try:
        # Add API key to params
        params["key"] = get_api_key()
        
        print(f"[DEBUG] Making request to: {url}", file=sys.stderr)
        print(f"[DEBUG] Params: {dict((k, v if k != 'key' else '***') for k, v in params.items())}", file=sys.stderr)
        
        with httpx.Client(timeout=30.0) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            # Check for Google Maps API error
            if data.get("status") != "OK":
                error_msg = data.get("error_message", f"API error: {data.get('status')}")
                result["error"] = error_msg
                print(f"[DEBUG] API Error: {error_msg}", file=sys.stderr)
                return result
            
            result["success"] = True
            result["data"] = data
            print(f"[DEBUG] Request successful", file=sys.stderr)
            
    except httpx.TimeoutException:
        result["error"] = "Request timed out"
        print(f"[DEBUG] Timeout error", file=sys.stderr)
    except httpx.HTTPStatusError as e:
        result["error"] = f"HTTP error {e.response.status_code}: {e.response.text}"
        print(f"[DEBUG] HTTP error: {result['error']}", file=sys.stderr)
    except Exception as e:
        result["error"] = f"Unexpected error: {str(e)}"
        print(f"[DEBUG] Unexpected error: {result['error']}", file=sys.stderr)
    
    return result


@mcp.tool()
def geocode(
    address: str = Field(description="Address or place name to convert to coordinates")
) -> Dict[str, Any]:
    """
    Convert an address to geographic coordinates.
    
    Args:
        address: The address or place name to geocode
        
    Returns:
        Dictionary containing coordinates and formatted address information
    """
    print(f"[DEBUG] Geocoding address: {address}", file=sys.stderr)
    
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"address": address}
    
    result = make_api_request(url, params)
    
    if result["success"]:
        geocode_data = result["data"]
        if geocode_data.get("results"):
            location_data = geocode_data["results"][0]
            location = location_data["geometry"]["location"]
            
            result["data"] = {
                "latitude": location["lat"],
                "longitude": location["lng"],
                "formatted_address": location_data["formatted_address"],
                "place_id": location_data.get("place_id"),
                "types": location_data.get("types", []),
                "address_components": location_data.get("address_components", [])
            }
            print(f"[DEBUG] Geocoded to: {location['lat']}, {location['lng']}", file=sys.stderr)
        else:
            result["success"] = False
            result["error"] = "No results found for the given address"
    
    return result


@mcp.tool()
def reverse_geocode(
    latitude: float = Field(description="Latitude coordinate"),
    longitude: float = Field(description="Longitude coordinate")
) -> Dict[str, Any]:
    """
    Convert coordinates to an address.
    
    Args:
        latitude: Latitude coordinate
        longitude: Longitude coordinate
        
    Returns:
        Dictionary containing address information for the coordinates
    """
    print(f"[DEBUG] Reverse geocoding: {latitude}, {longitude}", file=sys.stderr)
    
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"latlng": f"{latitude},{longitude}"}
    
    result = make_api_request(url, params)
    
    if result["success"]:
        geocode_data = result["data"]
        if geocode_data.get("results"):
            location_data = geocode_data["results"][0]
            
            result["data"] = {
                "formatted_address": location_data["formatted_address"],
                "place_id": location_data.get("place_id"),
                "types": location_data.get("types", []),
                "address_components": location_data.get("address_components", []),
                "all_results": [
                    {
                        "formatted_address": r["formatted_address"],
                        "types": r.get("types", [])
                    }
                    for r in geocode_data["results"][:5]  # Limit to first 5 results
                ]
            }
            print(f"[DEBUG] Reverse geocoded to: {location_data['formatted_address']}", file=sys.stderr)
        else:
            result["success"] = False
            result["error"] = "No results found for the given coordinates"
    
    return result


@mcp.tool()
def search_places(
    query: str = Field(description="Search query (e.g., 'restaurant', 'coffee shop near Times Square')"),
    location: str = Field(default="", description="Location bias as address or 'lat,lng' coordinates"),
    radius: int = Field(default=5000, description="Search radius in meters (max 50000)", le=50000, ge=1)
) -> Dict[str, Any]:
    """
    Search for places using Google Places API.
    
    Args:
        query: Search query for places
        location: Optional location bias (address or coordinates)
        radius: Search radius in meters
        
    Returns:
        Dictionary containing search results with place information
    """
    print(f"[DEBUG] Searching places: {query}, location: {location}, radius: {radius}", file=sys.stderr)
    
    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    params = {
        "query": query,
        "radius": radius
    }
    
    # Add location bias if provided
    if location:
        if "," in location and location.replace(",", "").replace(".", "").replace("-", "").isdigit():
            # Looks like coordinates
            params["location"] = location
        else:
            # Treat as address, need to geocode first
            geocode_result = geocode(location)
            if geocode_result["success"]:
                lat = geocode_result["data"]["latitude"]
                lng = geocode_result["data"]["longitude"]
                params["location"] = f"{lat},{lng}"
            else:
                print(f"[DEBUG] Could not geocode location bias: {location}", file=sys.stderr)
    
    result = make_api_request(url, params)
    
    if result["success"]:
        places_data = result["data"]
        places = []
        
        for place in places_data.get("results", []):
            place_info = {
                "name": place.get("name"),
                "place_id": place.get("place_id"),
                "formatted_address": place.get("formatted_address"),
                "rating": place.get("rating"),
                "user_ratings_total": place.get("user_ratings_total"),
                "price_level": place.get("price_level"),
                "types": place.get("types", []),
                "geometry": {
                    "location": place.get("geometry", {}).get("location", {})
                },
                "opening_hours": place.get("opening_hours", {}).get("open_now"),
                "photos": [photo.get("photo_reference") for photo in place.get("photos", [])[:3]]  # First 3 photos
            }
            places.append(place_info)
        
        result["data"] = {
            "places": places,
            "total_results": len(places),
            "next_page_token": places_data.get("next_page_token")
        }
        print(f"[DEBUG] Found {len(places)} places", file=sys.stderr)
    
    return result


@mcp.tool()
def get_place_details(
    place_id: str = Field(description="Google Maps Place ID"),
    fields: str = Field(default="basic", description="Detail level: 'basic', 'contact', or 'atmosphere'")
) -> Dict[str, Any]:
    """
    Get detailed information about a specific place.
    
    Args:
        place_id: Google Maps Place ID
        fields: Level of detail to retrieve
        
    Returns:
        Dictionary containing detailed place information
    """
    print(f"[DEBUG] Getting place details for: {place_id}, fields: {fields}", file=sys.stderr)
    
    # Define field sets
    field_sets = {
        "basic": "place_id,name,formatted_address,geometry,rating,user_ratings_total,types,price_level",
        "contact": "place_id,name,formatted_address,geometry,rating,user_ratings_total,types,price_level,formatted_phone_number,website,opening_hours",
        "atmosphere": "place_id,name,formatted_address,geometry,rating,user_ratings_total,types,price_level,formatted_phone_number,website,opening_hours,photos,reviews"
    }
    
    url = "https://maps.googleapis.com/maps/api/place/details/json"
    params = {
        "place_id": place_id,
        "fields": field_sets.get(fields, field_sets["basic"])
    }
    
    result = make_api_request(url, params)
    
    if result["success"]:
        place_data = result["data"].get("result", {})
        
        result["data"] = {
            "place_id": place_data.get("place_id"),
            "name": place_data.get("name"),
            "formatted_address": place_data.get("formatted_address"),
            "location": place_data.get("geometry", {}).get("location", {}),
            "rating": place_data.get("rating"),
            "user_ratings_total": place_data.get("user_ratings_total"),
            "types": place_data.get("types", []),
            "price_level": place_data.get("price_level"),
            "phone": place_data.get("formatted_phone_number"),
            "website": place_data.get("website"),
            "opening_hours": place_data.get("opening_hours", {}).get("weekday_text", []),
            "currently_open": place_data.get("opening_hours", {}).get("open_now"),
            "photos": [photo.get("photo_reference") for photo in place_data.get("photos", [])[:5]],
            "reviews": [
                {
                    "author_name": review.get("author_name"),
                    "rating": review.get("rating"),
                    "text": review.get("text"),
                    "time": review.get("time")
                }
                for review in place_data.get("reviews", [])[:3]
            ] if "reviews" in params["fields"] else []
        }
        print(f"[DEBUG] Retrieved details for: {place_data.get('name')}", file=sys.stderr)
    
    return result


@mcp.tool()
def get_directions(
    origin: str = Field(description="Starting point (address or coordinates)"),
    destination: str = Field(description="Destination (address or coordinates)"),
    mode: str = Field(default="driving", description="Travel mode: driving, walking, bicycling, transit")
) -> Dict[str, Any]:
    """
    Get directions between two locations.
    
    Args:
        origin: Starting location
        destination: Destination location  
        mode: Travel mode
        
    Returns:
        Dictionary containing turn-by-turn directions and route information
    """
    print(f"[DEBUG] Getting directions from {origin} to {destination}, mode: {mode}", file=sys.stderr)
    
    url = "https://maps.googleapis.com/maps/api/directions/json"
    params = {
        "origin": origin,
        "destination": destination,
        "mode": mode
    }
    
    result = make_api_request(url, params)
    
    if result["success"]:
        directions_data = result["data"]
        
        if directions_data.get("routes"):
            route = directions_data["routes"][0]
            leg = route["legs"][0]
            
            steps = []
            for step in leg.get("steps", []):
                steps.append({
                    "instruction": step.get("html_instructions", "").replace("<b>", "").replace("</b>", "").replace("<div>", " ").replace("</div>", ""),
                    "distance": step.get("distance", {}).get("text"),
                    "duration": step.get("duration", {}).get("text"),
                    "start_location": step.get("start_location"),
                    "end_location": step.get("end_location")
                })
            
            result["data"] = {
                "start_address": leg.get("start_address"),
                "end_address": leg.get("end_address"),
                "distance": leg.get("distance", {}).get("text"),
                "duration": leg.get("duration", {}).get("text"),
                "steps": steps,
                "polyline": route.get("overview_polyline", {}).get("points"),
                "bounds": route.get("bounds"),
                "warnings": route.get("warnings", [])
            }
            print(f"[DEBUG] Route found: {leg.get('distance', {}).get('text')}, {leg.get('duration', {}).get('text')}", file=sys.stderr)
        else:
            result["success"] = False
            result["error"] = "No route found"
    
    return result


@mcp.tool()
def get_distance_matrix(
    origins: List[str] = Field(description="List of origin locations"),
    destinations: List[str] = Field(description="List of destination locations"),
    mode: str = Field(default="driving", description="Travel mode: driving, walking, bicycling, transit")
) -> Dict[str, Any]:
    """
    Calculate distances and travel times between multiple origins and destinations.
    
    Args:
        origins: List of starting locations
        destinations: List of destination locations
        mode: Travel mode
        
    Returns:
        Dictionary containing distance/time matrix
    """
    print(f"[DEBUG] Getting distance matrix for {len(origins)} origins, {len(destinations)} destinations", file=sys.stderr)
    
    url = "https://maps.googleapis.com/maps/api/distancematrix/json"
    params = {
        "origins": "|".join(origins),
        "destinations": "|".join(destinations),
        "mode": mode
    }
    
    result = make_api_request(url, params)
    
    if result["success"]:
        matrix_data = result["data"]
        
        matrix_results = []
        for i, row in enumerate(matrix_data.get("rows", [])):
            origin_results = []
            for j, element in enumerate(row.get("elements", [])):
                origin_results.append({
                    "destination_index": j,
                    "status": element.get("status"),
                    "distance": element.get("distance", {}).get("text"),
                    "distance_value": element.get("distance", {}).get("value"),
                    "duration": element.get("duration", {}).get("text"),
                    "duration_value": element.get("duration", {}).get("value")
                })
            matrix_results.append({
                "origin_index": i,
                "results": origin_results
            })
        
        result["data"] = {
            "origin_addresses": matrix_data.get("origin_addresses", []),
            "destination_addresses": matrix_data.get("destination_addresses", []),
            "matrix": matrix_results
        }
        print(f"[DEBUG] Distance matrix calculated successfully", file=sys.stderr)
    
    return result


@mcp.tool()
def get_elevation(
    locations: List[Dict[str, float]] = Field(description="List of coordinates [{'latitude': float, 'longitude': float}]")
) -> Dict[str, Any]:
    """
    Get elevation data for one or more locations.
    
    Args:
        locations: List of coordinate dictionaries
        
    Returns:
        Dictionary containing elevation data for each location
    """
    print(f"[DEBUG] Getting elevation for {len(locations)} locations", file=sys.stderr)
    
    # Convert locations to lat,lng string format
    location_strings = []
    for loc in locations:
        location_strings.append(f"{loc['latitude']},{loc['longitude']}")
    
    url = "https://maps.googleapis.com/maps/api/elevation/json"
    params = {
        "locations": "|".join(location_strings)
    }
    
    result = make_api_request(url, params)
    
    if result["success"]:
        elevation_data = result["data"]
        
        elevations = []
        for i, elev_result in enumerate(elevation_data.get("results", [])):
            elevations.append({
                "location": elev_result.get("location"),
                "elevation": elev_result.get("elevation"),
                "resolution": elev_result.get("resolution"),
                "input_location": locations[i] if i < len(locations) else None
            })
        
        result["data"] = {
            "elevations": elevations,
            "total_results": len(elevations)
        }
        print(f"[DEBUG] Elevation data retrieved for {len(elevations)} locations", file=sys.stderr)
    
    return result


if __name__ == "__main__":
    mcp.run()