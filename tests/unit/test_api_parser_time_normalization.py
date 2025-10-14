"""Test time normalization in API parser for Issue #75.

Tests the fix for Spotify position/duration showing incorrect values.
See: https://github.com/mjcumming/wiim/issues/75
"""

import pytest

from custom_components.wiim.api_parser import _normalize_time_value, parse_player_status


class TestTimeNormalization:
    """Test time value normalization (milliseconds vs microseconds)."""

    def test_normalize_milliseconds_short_track(self):
        """Test normal millisecond values for short tracks."""
        # 3 minutes = 180 seconds = 180,000 milliseconds
        result = _normalize_time_value(180_000, "position")
        assert result == 180

    def test_normalize_milliseconds_long_track(self):
        """Test millisecond values for longer tracks (< 10 hour threshold)."""
        # 1 hour = 3600 seconds = 3,600,000 milliseconds
        result = _normalize_time_value(3_600_000, "duration")
        assert result == 3600

    def test_normalize_milliseconds_at_threshold(self):
        """Test value just under the 10-hour threshold (should use milliseconds)."""
        # 9.5 hours = 34,200 seconds = 34,200,000 milliseconds
        result = _normalize_time_value(34_200_000, "duration")
        assert result == 34_200

    def test_normalize_microseconds_spotify(self):
        """Test microsecond values from Spotify (over threshold)."""
        # 3 minutes = 180 seconds = 180,000,000 microseconds
        result = _normalize_time_value(180_000_000, "position")
        assert result == 180

    def test_normalize_microseconds_large_value(self):
        """Test the actual reported bug value from Issue #75."""
        # Reported: 488317:29:10 = ~1,757,942,360 seconds
        # In microseconds: 1,757,942,360,000,000
        # Code would incorrectly read as milliseconds: 1,757,942,360,000
        # Then convert to seconds: 1,757,942,360 (the bug!)
        bug_value_ms = 1_757_942_360_000  # What code sees if treating μs as ms
        result = _normalize_time_value(bug_value_ms, "position", "31")  # mode 31 = Spotify
        # Should correctly interpret as microseconds and convert to seconds
        assert result == 1_757_942  # ~488 hours (still wrong track, but showing detection works)

    def test_normalize_zero_value(self):
        """Test zero values (track start)."""
        result = _normalize_time_value(0, "position")
        assert result == 0

    def test_normalize_very_small_value(self):
        """Test very small values (< 1 second in milliseconds)."""
        result = _normalize_time_value(500, "position")  # 500ms = 0.5s
        assert result == 0  # Integer division

    def test_normalize_audiobook_length(self):
        """Test legitimate long-form content under threshold."""
        # 8 hours = 28,800 seconds = 28,800,000 milliseconds (under 10 hour threshold)
        result = _normalize_time_value(28_800_000, "duration")
        assert result == 28_800

    def test_normalize_with_source_hint(self):
        """Test normalization with source hint for logging."""
        # Should not affect calculation, just logging
        result = _normalize_time_value(180_000, "position", "31")  # Spotify
        assert result == 180


class TestParserIntegration:
    """Test full parser integration with time normalization."""

    def test_parse_status_normal_milliseconds(self):
        """Test parsing with normal millisecond values."""
        raw = {
            "status": "play",
            "curpos": "180000",  # 3 minutes in milliseconds
            "totlen": "240000",  # 4 minutes in milliseconds
            "vol": "50",
        }
        data, _ = parse_player_status(raw)

        assert data["position"] == 180
        assert data["duration"] == 240
        assert "position_updated_at" in data

    def test_parse_status_spotify_microseconds(self):
        """Test parsing with Spotify microsecond values (Issue #75)."""
        raw = {
            "status": "play",
            "mode": "31",  # Spotify mode
            "curpos": "180000000",  # 3 minutes in microseconds
            "totlen": "240000000",  # 4 minutes in microseconds
            "vol": "50",
            "Title": "Test Track",
        }
        data, _ = parse_player_status(raw)

        # Should correctly interpret as microseconds due to large values
        assert data["position"] == 180
        assert data["duration"] == 240
        assert "position_updated_at" in data

    def test_parse_status_mixed_values(self):
        """Test parsing where position and duration have different units (edge case)."""
        raw = {
            "status": "play",
            "curpos": "5000",  # 5 seconds in milliseconds (small value)
            "totlen": "240000000",  # 4 minutes in microseconds (large value)
            "vol": "50",
        }
        data, _ = parse_player_status(raw)

        # Each should be normalized independently
        assert data["position"] == 5  # milliseconds
        assert data["duration"] == 240  # microseconds

    def test_parse_status_zero_duration(self):
        """Test parsing with zero duration (streaming/unknown length)."""
        raw = {
            "status": "play",
            "curpos": "180000",
            "totlen": "0",  # Unknown/streaming
            "vol": "50",
        }
        data, _ = parse_player_status(raw)

        assert data["position"] == 180
        assert "duration" not in data  # Zero duration should not be set

    def test_parse_status_missing_position(self):
        """Test parsing when position fields are missing."""
        raw = {
            "status": "stop",
            "vol": "50",
        }
        data, _ = parse_player_status(raw)

        assert "position" not in data
        assert "duration" not in data

    def test_parse_status_offset_pts_fallback(self):
        """Test using offset_pts when curpos is not available."""
        raw = {
            "status": "play",
            "offset_pts": "180000",  # Alternative position field
            "totlen": "240000",
            "vol": "50",
        }
        data, _ = parse_player_status(raw)

        assert data["position"] == 180
        assert data["duration"] == 240

    def test_parse_status_invalid_values(self):
        """Test parsing with invalid time values."""
        raw = {
            "status": "play",
            "curpos": "invalid",
            "totlen": "not_a_number",
            "vol": "50",
        }
        data, _ = parse_player_status(raw)

        # Should not crash, just skip invalid values
        assert "position" not in data
        assert "duration" not in data

    def test_parse_status_negative_values(self):
        """Test parsing with negative values (should be handled gracefully)."""
        raw = {
            "status": "play",
            "curpos": "-1000",
            "totlen": "-5000",
            "vol": "50",
        }
        data, _ = parse_player_status(raw)

        # Implementation should handle this - might skip or use abs()
        # Current implementation doesn't validate negative, so will process them
        # This test documents current behavior
        if "position" in data:
            # If processed, verify it doesn't crash
            assert isinstance(data["position"], int)


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_exactly_at_threshold(self):
        """Test value exactly at the 10-hour threshold."""
        # 10 hours = 36,000,000 milliseconds
        threshold = 36_000_000

        # Just under threshold - should use milliseconds
        result_under = _normalize_time_value(threshold - 1, "duration")
        assert result_under == (threshold - 1) // 1_000

        # At threshold - should use milliseconds (> not >=)
        result_at = _normalize_time_value(threshold, "duration")
        assert result_at == threshold // 1_000

        # Just over threshold - should use microseconds
        result_over = _normalize_time_value(threshold + 1, "duration")
        assert result_over == (threshold + 1) // 1_000_000

    def test_maximum_int_value(self):
        """Test with very large values (within int range)."""
        # Large microsecond value
        large_val = 999_999_999_999  # ~277 hours
        result = _normalize_time_value(large_val, "duration")
        assert result == 999_999  # Should use microsecond conversion

    def test_field_name_parameter(self):
        """Test that field_name parameter is used correctly (affects logging only)."""
        # Should work with different field names
        result1 = _normalize_time_value(180_000, "position")
        result2 = _normalize_time_value(180_000, "duration")
        result3 = _normalize_time_value(180_000, "seek")

        assert result1 == result2 == result3 == 180


class TestRealWorldScenarios:
    """Test real-world streaming service scenarios."""

    def test_spotify_typical_song(self):
        """Test typical Spotify song (3:30 = 210 seconds)."""
        # Spotify returns microseconds
        spotify_value = 210_000_000  # 210 seconds in microseconds
        result = _normalize_time_value(spotify_value, "position", "31")
        assert result == 210

    def test_local_file_typical_song(self):
        """Test local file playback (3:30 = 210 seconds)."""
        # Local files likely use milliseconds
        local_value = 210_000  # 210 seconds in milliseconds
        result = _normalize_time_value(local_value, "position")
        assert result == 210

    def test_streaming_no_duration(self):
        """Test live streaming with unknown duration."""
        raw = {
            "status": "play",
            "mode": "31",  # Spotify
            "curpos": "60000000",  # 1 minute in microseconds
            "totlen": "0",  # Unknown/streaming
            "vol": "50",
        }
        data, _ = parse_player_status(raw)

        assert data["position"] == 60
        assert "duration" not in data

    def test_podcast_episode(self):
        """Test long-form content like podcast (2 hours)."""
        # 2 hours = 7200 seconds in milliseconds (under threshold)
        podcast_value = 7_200_000
        result = _normalize_time_value(podcast_value, "duration")
        assert result == 7200

    def test_audiobook_chapter(self):
        """Test very long audiobook chapter (5 hours)."""
        # 5 hours = 18,000 seconds = 18,000,000 milliseconds (under threshold)
        audiobook_value = 18_000_000
        result = _normalize_time_value(audiobook_value, "duration")
        assert result == 18_000


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

