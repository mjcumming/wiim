# Changelog

All notable changes to the WiiM Audio integration will be documented in this file.

## [v2.0.1] - 2024-12-19

### 🐛 Critical Production Bug Fixes

- 🎵 **Fixed unknown play state 'none'** - Added 'none' to transitional states, eliminating 5,967+ recurring errors
- 🔗 **Improved master/slave detection** - Enhanced master finding logic with IP-based lookup and better fallbacks, reducing 1,985+ errors
- 👥 **Better group join validation** - Improved error messages and entity resolution for multiroom grouping failures
- 🔇 **Rate-limited error logging** - Reduced log spam by limiting repeated warnings to once per 5 minutes
- 🛠️ **Enhanced debugging info** - Better error messages with available entity information for troubleshooting

### 📊 Impact

- **Eliminated 7,952+ recurring errors** from production logs
- **Improved multiroom stability** with better master/slave relationship handling
- **Reduced log spam** while maintaining debugging capability
