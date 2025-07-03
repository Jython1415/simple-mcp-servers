# ROADMAP

1. Deal with issue:

⏺ obsidian-vault:obsidian_list_notes (MCP)(directory: "", file_extension_filter: ".md", max_depth:
                                           2)
  ⎿  Error: MCP tool "obsidian_list_notes" response (62025 tokens) exceeds maximum allowed tokens
     (25000). Please use pagination, filtering, or limit parameters to reduce the response size.

✅ **ISSUE #1 RESOLVED**: obsidian-vault token limit fixed
- Added max_files=100 and lazy_parsing=True parameters
- Maintained backward compatibility
- Added truncation metadata

2. Process temp_lessons/* into memory file - multiple lessons about MCP development

