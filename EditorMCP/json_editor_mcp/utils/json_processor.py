"""JSON processing utilities for converting between JSON and editable map format."""

import copy
import hashlib
import json
from typing import Any, Dict, List, Tuple, Union

from ..models.core import MapEntry, ProposedChange


class JSONProcessingError(Exception):
    """Base exception for JSON processing errors."""
    pass


class InvalidJSONError(JSONProcessingError):
    """Raised when JSON document is invalid or cannot be parsed."""
    pass


class MapConversionError(JSONProcessingError):
    """Raised when map conversion fails."""
    pass


class JSONProcessor:
    """Handles conversion between JSON documents and editable map format."""
    
    def __init__(self):
        """Initialize the JSON processor."""
        pass
    
    def json2map(self, document: Dict[str, Any]) -> List[MapEntry]:
        """
        Convert a JSON document to a list of editable map entries.
        
        Args:
            document: JSON document to convert
            
        Returns:
            List of MapEntry objects representing editable text nodes
            
        Raises:
            InvalidJSONError: If document is invalid
            MapConversionError: If conversion fails
        """
        try:
            if not isinstance(document, dict):
                raise InvalidJSONError("Document must be a dictionary")
            
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
                    # Check if this is a text node that should be editable
                    if node.get("type") in ["text", "Text", "Placeholder"] and "value" in node:
                        try:
                            map_entry = MapEntry(
                                id=_next_id(),
                                path=path + ["value"],
                                value=str(node["value"])
                            )
                            out.append(map_entry)
                        except Exception as e:
                            raise MapConversionError(f"Failed to create MapEntry: {e}")
                    else:
                        # Push children in reverse order for left->right traversal
                        for k in sorted(node.keys(), reverse=True):
                            stack.append((node[k], path + [k]))
                elif isinstance(node, list):
                    # Process list items in reverse order
                    for idx, item in enumerate(reversed(node)):
                        stack.append((item, path + [str(len(node) - 1 - idx)]))
            
            return out
            
        except InvalidJSONError:
            raise
        except MapConversionError:
            raise
        except Exception as e:
            raise MapConversionError(f"Unexpected error during JSON to map conversion: {e}")
    
    def map2json(self, original: Dict[str, Any], updated_map: List[MapEntry]) -> Dict[str, Any]:
        """
        Reconstruct JSON document from original and updated map entries.
        
        Args:
            original: Original JSON document
            updated_map: List of updated map entries
            
        Returns:
            Modified JSON document
            
        Raises:
            InvalidJSONError: If original document is invalid
            MapConversionError: If reconstruction fails
        """
        try:
            if not isinstance(original, dict):
                raise InvalidJSONError("Original document must be a dictionary")
            
            # Deep clone the original document
            doc = copy.deepcopy(original)
            
            # Apply each updated entry
            for entry in updated_map:
                try:
                    self._apply_map_entry(doc, entry)
                except Exception as e:
                    raise MapConversionError(f"Failed to apply map entry {entry.id}: {e}")
            
            return doc
            
        except InvalidJSONError:
            raise
        except MapConversionError:
            raise
        except Exception as e:
            raise MapConversionError(f"Unexpected error during map to JSON conversion: {e}")
    
    def _apply_map_entry(self, doc: Dict[str, Any], entry: MapEntry) -> None:
        """
        Apply a single map entry to the document.
        
        Args:
            doc: Document to modify (modified in place)
            entry: Map entry to apply
            
        Raises:
            MapConversionError: If path is invalid or application fails
        """
        if not entry.path:
            raise MapConversionError(f"Empty path for entry {entry.id}")
        
        try:
            # Navigate to the parent of the target
            walk = doc
            *parents, last = entry.path
            
            for step in parents:
                if step.isdigit():
                    # Array index
                    idx = int(step)
                    if not isinstance(walk, list):
                        raise MapConversionError(f"Expected list at path step '{step}', got {type(walk)}")
                    if idx >= len(walk):
                        raise MapConversionError(f"Array index {idx} out of bounds (length: {len(walk)})")
                    walk = walk[idx]
                else:
                    # Object key
                    if not isinstance(walk, dict):
                        raise MapConversionError(f"Expected dict at path step '{step}', got {type(walk)}")
                    if step not in walk:
                        raise MapConversionError(f"Key '{step}' not found in object")
                    walk = walk[step]
            
            # Apply the final value
            if last.isdigit():
                # Array index
                idx = int(last)
                if not isinstance(walk, list):
                    raise MapConversionError(f"Expected list at final path step '{last}', got {type(walk)}")
                if idx >= len(walk):
                    raise MapConversionError(f"Array index {idx} out of bounds (length: {len(walk)})")
                walk[idx] = entry.value
            else:
                # Object key
                if not isinstance(walk, dict):
                    raise MapConversionError(f"Expected dict at final path step '{last}', got {type(walk)}")
                walk[last] = entry.value
                
        except (ValueError, KeyError, IndexError, TypeError) as e:
            raise MapConversionError(f"Path navigation failed for entry {entry.id}: {e}")
    
    def generate_document_hash(self, document: Dict[str, Any]) -> str:
        """
        Generate a hash for a JSON document to track changes.
        
        Args:
            document: JSON document to hash
            
        Returns:
            SHA-256 hash of the document
            
        Raises:
            InvalidJSONError: If document cannot be serialized
        """
        try:
            # Convert to JSON string with sorted keys for consistent hashing
            json_str = json.dumps(document, sort_keys=True, separators=(',', ':'))
            return hashlib.sha256(json_str.encode('utf-8')).hexdigest()
        except (TypeError, ValueError) as e:
            raise InvalidJSONError(f"Cannot serialize document for hashing: {e}")
    
    def validate_json_document(self, document: Any) -> Dict[str, Any]:
        """
        Validate that a document is a valid JSON object.
        
        Args:
            document: Document to validate
            
        Returns:
            The validated document
            
        Raises:
            InvalidJSONError: If document is not valid JSON
        """
        if not isinstance(document, dict):
            raise InvalidJSONError("Document must be a JSON object (dictionary)")
        
        try:
            # Try to serialize and deserialize to ensure it's valid JSON
            json_str = json.dumps(document)
            json.loads(json_str)
            return document
        except (TypeError, ValueError) as e:
            raise InvalidJSONError(f"Document is not valid JSON: {e}")
    
    def create_change_preview(self, original_map: List[MapEntry], updated_map: List[MapEntry]) -> List[ProposedChange]:
        """
        Create a preview of changes between original and updated map entries.
        
        Args:
            original_map: Original map entries
            updated_map: Updated map entries
            
        Returns:
            List of proposed changes
            
        Raises:
            MapConversionError: If change detection fails
        """
        try:
            changes = []
            
            # Create lookup dictionaries for efficient comparison
            original_lookup = {entry.id: entry for entry in original_map}
            updated_lookup = {entry.id: entry for entry in updated_map}
            
            # Find changes
            for entry_id, updated_entry in updated_lookup.items():
                if entry_id in original_lookup:
                    original_entry = original_lookup[entry_id]
                    if original_entry.value != updated_entry.value:
                        # Value changed
                        change = ProposedChange(
                            id=entry_id,
                            path=updated_entry.path,
                            current_value=original_entry.value,
                            proposed_value=updated_entry.value,
                            confidence=1.0
                        )
                        changes.append(change)
                else:
                    # New entry (shouldn't happen in normal flow, but handle gracefully)
                    change = ProposedChange(
                        id=entry_id,
                        path=updated_entry.path,
                        current_value="",
                        proposed_value=updated_entry.value,
                        confidence=1.0
                    )
                    changes.append(change)
            
            return changes
            
        except Exception as e:
            raise MapConversionError(f"Failed to create change preview: {e}")