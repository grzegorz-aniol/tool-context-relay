---
id: web1
tool_calls:
  - tool_name: get_page
    opaque_id_result: true
  - tool_name: internal_resource_grep
    opaque_id_input: true
    allow_multiple: true
forbidden_tools:
  - internal_resource_read
---
Find all image elements in a HTML content at: https://demo.local/history

The page may be huge, use optimal tool usage to find it without exposing full page content.
