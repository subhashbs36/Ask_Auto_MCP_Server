# API Documentation - MCP Tool Schemas

## Overview

The JSON Editor MCP Tool provides two main tools through the Model Context Protocol (MCP):
- `json_editor_preview`: Preview proposed changes to a JSON document
- `json_editor_apply`: Apply previously previewed changes

## Tool Schemas

### json_editor_preview

**Description:** Preview proposed changes to a JSON document using natural language instructions without modifying the original document.

**Input Schema:**
```json
{
  "name": "json_editor_preview",
  "description": "Preview proposed changes to a JSON document using natural language instructions",
  "inputSchema": {
    "type": "object",
    "properties": {
      "document": {
        "type": "object",
        "description": "JSON document to edit. Can be any valid JSON structure (object, array, etc.)"
      },
      "instruction": {
        "type": "string",
        "description": "Natural language editing instruction describing what changes to make",
        "minLength": 1,
        "maxLength": 1000
      }
    },
    "required": ["document", "instruction"],
    "additionalProperties": false
  }
}
```

**Output Schema:**
```json
{
  "type": "object",
  "properties": {
    "session_id": {
      "type": "string",
      "description": "Unique session identifier for applying changes later"
    },
    "changes": {
      "type": "array",
      "description": "List of proposed changes",
      "items": {
        "type": "object",
        "properties": {
          "id": {
            "type": "string",
            "description": "Unique identifier for this change"
          },
          "path": {
            "type": "array",
            "items": {"type": "string"},
            "description": "JSON path to the field being changed"
          },
          "current_value": {
            "type": "string",
            "description": "Current value at this path"
          },
          "proposed_value": {
            "type": "string",
            "description": "Proposed new value"
          },
          "confidence": {
            "type": "number",
            "minimum": 0,
            "maximum": 1,
            "description": "Confidence score for this change (0.0 to 1.0)"
          }
        },
        "required": ["id", "path", "current_value", "proposed_value"]
      }
    },
    "message": {
      "type": "string",
      "description": "Human-readable message about the preview results"
    },
    "status": {
      "type": "string",
      "enum": ["success", "no_changes", "ambiguous"],
      "description": "Status of the preview operation"
    },
    "suggestions": {
      "type": "array",
      "items": {"type": "string"},
      "description": "Suggestions for clearer instructions (when status is 'ambiguous')"
    }
  },
  "required": ["session_id", "changes", "message", "status"]
}
```

### json_editor_apply

**Description:** Apply previously previewed changes to a JSON document using the session ID from a preview operation.

**Input Schema:**
```json
{
  "name": "json_editor_apply",
  "description": "Apply previously previewed changes to a JSON document",
  "inputSchema": {
    "type": "object",
    "properties": {
      "session_id": {
        "type": "string",
        "description": "Session ID from the corresponding preview operation",
        "pattern": "^[a-zA-Z0-9_-]+$"
      },
      "confirmed_changes": {
        "type": "array",
        "items": {"type": "string"},
        "description": "Optional list of change IDs to apply. If omitted, all changes are applied"
      }
    },
    "required": ["session_id"],
    "additionalProperties": false
  }
}
```

**Output Schema:**
```json
{
  "type": "object",
  "properties": {
    "modified_document": {
      "type": "object",
      "description": "The JSON document with changes applied"
    },
    "applied_changes": {
      "type": "array",
      "description": "List of changes that were actually applied",
      "items": {
        "type": "object",
        "properties": {
          "id": {
            "type": "string",
            "description": "Change identifier"
          },
          "path": {
            "type": "array",
            "items": {"type": "string"},
            "description": "JSON path where change was applied"
          },
          "old_value": {
            "type": "string",
            "description": "Previous value before change"
          },
          "new_value": {
            "type": "string",
            "description": "New value after change"
          },
          "applied_at": {
            "type": "string",
            "format": "date-time",
            "description": "Timestamp when change was applied"
          }
        },
        "required": ["id", "path", "old_value", "new_value", "applied_at"]
      }
    },
    "message": {
      "type": "string",
      "description": "Human-readable message about the apply results"
    },
    "status": {
      "type": "string",
      "enum": ["success", "partial_success", "failed"],
      "description": "Status of the apply operation"
    }
  },
  "required": ["modified_document", "applied_changes", "message", "status"]
}
```

## Error Responses

All tools return standardized MCP error responses when operations fail:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "data": {
      "error_type": "validation|llm_service|session|processing",
      "details": {
        "field": "specific_field_name",
        "reason": "detailed_reason"
      },
      "suggestions": ["suggestion1", "suggestion2"],
      "debug_info": {
        "request_id": "unique_request_id",
        "timestamp": "2024-01-01T00:00:00Z"
      }
    }
  }
}
```

### Error Codes

| Code | Type | Description |
|------|------|-------------|
| `INVALID_INPUT` | validation | Invalid or missing required parameters |
| `INVALID_JSON` | validation | Malformed JSON document |
| `DOCUMENT_TOO_LARGE` | validation | Document exceeds size limits |
| `INSTRUCTION_TOO_LONG` | validation | Instruction exceeds length limits |
| `LLM_SERVICE_ERROR` | llm_service | LLM provider API error |
| `LLM_RATE_LIMIT` | llm_service | Rate limit exceeded |
| `LLM_TIMEOUT` | llm_service | Request timeout |
| `SESSION_NOT_FOUND` | session | Invalid or expired session ID |
| `DOCUMENT_CHANGED` | session | Document modified since preview |
| `PROCESSING_ERROR` | processing | Internal processing error |
| `REDIS_CONNECTION_ERROR` | processing | Redis connection failure |

## Usage Examples

### Example 1: Simple Field Update

**Preview Request:**
```json
{
  "tool": "json_editor_preview",
  "arguments": {
    "document": {
      "name": "John Doe",
      "age": 30,
      "email": "john@example.com"
    },
    "instruction": "Update the email to john.doe@newcompany.com"
  }
}
```

**Preview Response:**
```json
{
  "session_id": "sess_abc123def456",
  "changes": [
    {
      "id": "change_001",
      "path": ["email"],
      "current_value": "john@example.com",
      "proposed_value": "john.doe@newcompany.com",
      "confidence": 0.95
    }
  ],
  "message": "Found 1 change to apply",
  "status": "success"
}
```

**Apply Request:**
```json
{
  "tool": "json_editor_apply",
  "arguments": {
    "session_id": "sess_abc123def456"
  }
}
```

**Apply Response:**
```json
{
  "modified_document": {
    "name": "John Doe",
    "age": 30,
    "email": "john.doe@newcompany.com"
  },
  "applied_changes": [
    {
      "id": "change_001",
      "path": ["email"],
      "old_value": "john@example.com",
      "new_value": "john.doe@newcompany.com",
      "applied_at": "2024-01-01T12:00:00Z"
    }
  ],
  "message": "Successfully applied 1 change",
  "status": "success"
}
```

### Example 2: Complex Nested Structure

**Preview Request:**
```json
{
  "tool": "json_editor_preview",
  "arguments": {
    "document": {
      "users": [
        {
          "id": 1,
          "profile": {
            "name": "Alice Smith",
            "settings": {
              "theme": "dark",
              "notifications": true
            }
          }
        },
        {
          "id": 2,
          "profile": {
            "name": "Bob Johnson",
            "settings": {
              "theme": "light",
              "notifications": false
            }
          }
        }
      ]
    },
    "instruction": "Change Alice's theme to light and enable Bob's notifications"
  }
}
```

**Preview Response:**
```json
{
  "session_id": "sess_xyz789abc123",
  "changes": [
    {
      "id": "change_001",
      "path": ["users", "0", "profile", "settings", "theme"],
      "current_value": "dark",
      "proposed_value": "light",
      "confidence": 0.92
    },
    {
      "id": "change_002",
      "path": ["users", "1", "profile", "settings", "notifications"],
      "current_value": "false",
      "proposed_value": "true",
      "confidence": 0.88
    }
  ],
  "message": "Found 2 changes to apply",
  "status": "success"
}
```

### Example 3: Ambiguous Instruction

**Preview Request:**
```json
{
  "tool": "json_editor_preview",
  "arguments": {
    "document": {
      "products": [
        {"name": "Widget A", "price": 10.99},
        {"name": "Widget B", "price": 15.99},
        {"name": "Gadget C", "price": 25.99}
      ]
    },
    "instruction": "Update the price"
  }
}
```

**Preview Response:**
```json
{
  "session_id": "sess_ambiguous123",
  "changes": [],
  "message": "Instruction is ambiguous - multiple price fields found",
  "status": "ambiguous",
  "suggestions": [
    "Specify which product's price to update (e.g., 'Update Widget A price to 12.99')",
    "Specify all prices to update (e.g., 'Increase all prices by 10%')",
    "Use more specific field references"
  ]
}
```

### Example 4: Error Response

**Preview Request with Invalid JSON:**
```json
{
  "tool": "json_editor_preview",
  "arguments": {
    "document": "invalid json string",
    "instruction": "Update something"
  }
}
```

**Error Response:**
```json
{
  "error": {
    "code": "INVALID_INPUT",
    "message": "Document must be a valid JSON object",
    "data": {
      "error_type": "validation",
      "details": {
        "field": "document",
        "reason": "Expected object, received string"
      },
      "suggestions": [
        "Ensure the document parameter contains a valid JSON object",
        "Check that the JSON is properly formatted"
      ],
      "debug_info": {
        "request_id": "req_error123",
        "timestamp": "2024-01-01T12:00:00Z"
      }
    }
  }
}
```

## Integration Guidelines

### For MCP Clients

1. **Always call preview first**: Never call apply without a corresponding preview
2. **Handle session expiration**: Be prepared to regenerate previews if sessions expire
3. **Validate responses**: Check the status field and handle different response types
4. **Present changes clearly**: Show users exactly what will change before applying
5. **Handle errors gracefully**: Provide meaningful error messages to users

### For EditAgent Integration

```python
async def edit_json_document(document: dict, instruction: str) -> dict:
    """
    EditAgent integration example
    """
    # Step 1: Preview changes
    preview_response = await mcp_client.call_tool(
        "json_editor_preview",
        {"document": document, "instruction": instruction}
    )
    
    if preview_response["status"] == "ambiguous":
        # Handle ambiguous instructions
        raise AmbiguousInstructionError(
            preview_response["message"],
            suggestions=preview_response.get("suggestions", [])
        )
    
    if not preview_response["changes"]:
        # No changes needed
        return document
    
    # Step 2: Present changes to user (EditAgent handles this)
    user_confirmed = await present_changes_to_user(preview_response["changes"])
    
    if not user_confirmed:
        return document
    
    # Step 3: Apply changes
    apply_response = await mcp_client.call_tool(
        "json_editor_apply",
        {"session_id": preview_response["session_id"]}
    )
    
    return apply_response["modified_document"]
```

### Rate Limiting Considerations

- LLM providers have rate limits that may affect response times
- Implement client-side retry logic with exponential backoff
- Consider caching preview results for identical requests
- Monitor rate limit headers and adjust request patterns accordingly

### Security Best Practices

- Validate all input documents before sending to the tool
- Sanitize instruction text to prevent prompt injection
- Implement request size limits on the client side
- Log security-relevant events for audit purposes
- Use secure connections (HTTPS) for all API communications