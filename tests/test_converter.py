"""
Tests for the deer_to_bsky_mcp package.
"""

import pytest
from deer_to_bsky_mcp.app import convert_deer_to_bluesky


def test_convert_profile_post_url():
    """Test conversion of a profile post URL."""
    deer_url = "https://deer.social/profile/did:plc:h25avmes6g7fgcddc3xj7qmg/post/3loxuoxb5ts2w"
    expected = "at://did:plc:h25avmes6g7fgcddc3xj7qmg/app.bsky.feed.post/3loxuoxb5ts2w"
    
    result = convert_deer_to_bluesky(deer_url)
    assert result == expected


def test_convert_profile_url():
    """Test conversion of a profile URL."""
    deer_url = "https://deer.social/profile/did:plc:h25avmes6g7fgcddc3xj7qmg"
    expected = "at://did:plc:h25avmes6g7fgcddc3xj7qmg"
    
    result = convert_deer_to_bluesky(deer_url)
    assert result == expected


def test_invalid_url():
    """Test conversion of an invalid URL."""
    deer_url = "https://deer.social/invalid/url"
    
    result = convert_deer_to_bluesky(deer_url)
    assert result is None


if __name__ == "__main__":
    # Simple test runner
    test_convert_profile_post_url()
    test_convert_profile_url()
    test_invalid_url()
    print("All tests passed!")
