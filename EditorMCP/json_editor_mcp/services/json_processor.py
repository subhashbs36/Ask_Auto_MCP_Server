"""JSON processing service for converting between JSON and editable map format."""

import copy
import hashlib
import json
from typing import Any, Dict, List, Tuple

from ..models.core import MapEntry
from ..models.errors import ProcessingException


class JSONProcessor:
    """Service for processing JSON documents and converting to/from map format."""
    
    def json2map(self, document: Dict[str, Any]) -> List[MapEntry]:
        """
        Convert JSON document to a list of MapEntry objects for editable text nodes.
        
        Args:
            document: JSON document to convert
            
        Returns:
            List of MapEntry objects representing editable text nodes
            
        Raises:
            ProcessingError: If document processing fails
        """
        try:
            counter = 0
            stack: List[Tuple[Any, List[str]]] = [(document, [])]
            out: List[MapEntry] = []
            
            def _next_id() -> str:
                nonlocal counter
                cid = f"t{counter}"
                counter += 1
                return cid
            
            while stack:
                node, path = stack.pop()
                
                if isinstance(node, dict):
                    # Check if this is an editable text node
                    if node.get("type") in ["text", "Text", "Placeholder"] and "value" in node:
                        out.append(MapEntry(
                            id=_next_id(),
                            path=path + ["value"],
                            value=str(node["value"])
                        ))
                    else:
                        # Push children in reverse order for left->right traversal
                        for k in sorted(node.keys(), reverse=True):
                            stack.append((node[k], path + [k]))
                elif isinstance(node, list):
                    # Process list items in reverse order for correct traversal
                    for idx, item in enumerate(reversed(node)):
                        stack.append((item, path + [str(len(node) - 1 - idx)]))
            
            return out
            
        except Exception as e:
            raise ProcessingException(
                error_code="JSON_TO_MAP_FAILED",
                message=f"Failed to convert JSON to map format: {str(e)}",
                details={"error": str(e)}
            )
    
    def map2json(self, original: Dict[str, Any], updated_map: List[MapEntry]) -> Dict[str, Any]:
        """
        Reconstruct JSON document from original and updated map entries.
        
        Args:
            original: Original JSON document
            updated_map: List of MapEntry objects with updated values
            
        Returns:
            Reconstructed JSON document with applied changes
            
        Raises:
            ProcessingError: If document reconstruction fails
        """
        try:
            # Deep clone the original document
            doc = copy.deepcopy(original)
            
            # Apply each updated entry
            for entry in updated_map:
                try:
                    walk = doc
                    *parents, last = entry.path
                    
                    # Navigate to the parent of the target value
                    for step in parents:
                        if step.isdigit():
                            walk = walk[int(step)]
                        else:
                            walk = walk[step]
                    
                    # Set the final value
                    if last.isdigit():
                        walk[int(last)] = entry.value
                    else:
                        walk[last] = entry.value
                        
                except (KeyError, IndexError, TypeError) as e:
                    raise ProcessingException(
                        error_code="INVALID_PATH",
                        message=f"Invalid path in map entry {entry.id}: {' -> '.join(entry.path)}",
                        details={
                            "entry_id": entry.id,
                            "path": entry.path,
                            "error": str(e)
                        }
                    )
            
            return doc
            
        except ProcessingException:
            # Re-raise ProcessingException as-is
            raise
        except Exception as e:
            raise ProcessingException(
                error_code="MAP_TO_JSON_FAILED",
                message=f"Failed to reconstruct JSON from map: {str(e)}",
                details={"error": str(e)}
            )
    
    def generate_document_hash(self, document: Dict[str, Any]) -> str:
        """
        Generate a hash for the document to track changes.
        
        Args:
            document: JSON document to hash
            
        Returns:
            SHA-256 hash of the document as hex string
            
        Raises:
            ProcessingError: If hash generation fails
        """
        try:
            # Convert document to canonical JSON string for consistent hashing
            json_str = json.dumps(document, sort_keys=True, separators=(',', ':'))
            
            # Generate SHA-256 hash
            hash_obj = hashlib.sha256(json_str.encode('utf-8'))
            return hash_obj.hexdigest()
            
        except Exception as e:
            raise ProcessingException(
                error_code="HASH_GENERATION_FAILED",
                message=f"Failed to generate document hash: {str(e)}",
                details={"error": str(e)}
            )
    
    def validate_json(self, data: Any) -> Dict[str, Any]:
        """
        Validate that the input is a valid JSON document (dict).
        
        Args:
            data: Data to validate
            
        Returns:
            The validated JSON document
            
        Raises:
            ProcessingError: If validation fails
        """
        if not isinstance(data, dict):
            raise ProcessingException(
                error_code="INVALID_JSON_TYPE",
                message="Document must be a JSON object (dict)",
                details={"received_type": type(data).__name__}
            )
        
        try:
            # Test that the document can be serialized to JSON
            json.dumps(data)
            return data
        except (TypeError, ValueError) as e:
            raise ProcessingException(
                error_code="JSON_SERIALIZATION_FAILED",
                message=f"Document contains non-serializable data: {str(e)}",
                details={"error": str(e)}
            )
    
    def parse_json_string(self, json_str: str) -> Dict[str, Any]:
        """
        Parse a JSON string into a document.
        
        Args:
            json_str: JSON string to parse
            
        Returns:
            Parsed JSON document
            
        Raises:
            ProcessingException: If parsing fails
        """
        try:
            data = json.loads(json_str)
            return self.validate_json(data)
        except json.JSONDecodeError as e:
            raise ProcessingException(
                error_code="JSON_PARSE_FAILED",
                message=f"Invalid JSON string: {str(e)}",
                details={
                    "error": str(e),
                    "line": getattr(e, 'lineno', None),
                    "column": getattr(e, 'colno', None)
                }
            )
        except ProcessingException:
            # Re-raise ProcessingException as-is (from validate_json)
            raise
        except Exception as e:
            raise ProcessingException(
                error_code="JSON_PARSE_ERROR",
                message=f"Unexpected error parsing JSON: {str(e)}",
                details={"error": str(e)}
            )