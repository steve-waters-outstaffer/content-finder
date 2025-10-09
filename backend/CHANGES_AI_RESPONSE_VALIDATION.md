# AI Response Validation & Error Handling Improvements

**Date:** 2025-09-30
**Issue:** Gemini API returning empty/malformed responses causing silent discovery failures

## Changes Made

### 1. Stricter Prompt Instructions

**File:** `intelligence/config/prompts/voc_reddit_batch_prescore.txt`
- Added explicit JSON format requirements
- Specified required keys and data types
- Added fallback instructions for uncertain cases
- Emphasized "no markdown fences" requirement
- Specified array length must match post count

**File:** `intelligence/config/prompts/voc_reddit_analysis_prompt.txt`
- Added strict JSON object requirements
- Defined exact key names and value types
- Provided fallback response template
- Emphasized single valid JSON object output

### 2. Response Validation Functions

**File:** `intelligence/voc_discovery.py`

Added two new validation functions:

**`_validate_batch_prescore_response(parsed, expected_count)`**
- Validates response is a list
- Checks array length matches expected post count
- Validates each item has required keys: `post_index`, `relevance_score`, `quick_reason`
- Type checks: `post_index` must be int, `relevance_score` must be numeric
- Logs specific validation failures

**`_validate_reddit_analysis_response(parsed)`**
- Validates response is a dict
- Checks all required keys present: `relevance_score`, `reasoning`, `identified_pain_point`, `outstaffer_solution_angle`
- Type checks: `relevance_score` must be numeric
- Logs specific validation failures

### 3. Enhanced Error Handling & Logging

**Batch Prescore (`_prescore_posts_batch`)**
- Check for empty response before parsing
- Log prompt preview and post count on empty response
- Debug log first 500 chars of raw response
- Validate structure before processing
- Log raw response on validation failure

**Reddit Analysis (`_enrich_post_with_reddit_comments`)**
- Check for empty response before parsing
- Log prompt preview and post title on empty response
- Debug log first 300 chars of raw response
- Validate structure before using
- Log raw response on validation failure
- Changed logger.warning to logger.error for failed analyses

**JSON Parser (`_normalise_json_response`)**
- Enhanced to handle both JSON objects and arrays
- Try array parsing if object parsing fails
- Better fallback handling for markdown-wrapped responses

## Expected Outcomes

### Better Debugging
- Clear error messages identifying exactly what went wrong
- Sample of raw AI response in logs for manual inspection
- Specific validation failures (missing keys, wrong types, etc.)

### More Robust Processing
- Validation catches malformed responses before they cause downstream issues
- Graceful degradation with neutral scores when AI fails
- No silent failures - all issues are logged as errors

### Faster Issue Resolution
- Logs now contain actionable information
- Can identify if issue is: empty response, malformed JSON, wrong structure, or missing keys
- Prompt previews help debug AI instruction issues

## Testing

After deployment, monitor logs for:
1. Reduction in "Empty response from Gemini" errors
2. New validation error messages showing specific issues
3. Better recovery from AI failures

## Rollback Plan

If issues arise:
1. Revert prompt files to previous versions (simpler instructions)
2. Remove validation function calls (keep functions for future use)
3. Revert enhanced logging if too verbose

## Future Improvements

Consider:
- Retry logic with exponential backoff for empty responses
- Alternative AI provider fallback
- Response caching to reduce API calls
- Batch size tuning based on failure rates
