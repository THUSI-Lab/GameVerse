"""
Reflection Manager: Save and load experience extracted from video reflections
"""
import os
import json
import logging
import re
from pathlib import Path
from typing import Optional, Dict, List, Tuple

logger = logging.getLogger(__name__)


class ReflectionManager:
    """Class for managing game experience/reflections"""
    
    def __init__(self, base_path: str = "data/reflections"):
        """
        Initialize the reflection manager
        
        Args:
            base_path: Base path for saving reflections
        """
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def get_reflection_path(self, game_name: str, format: str = "json") -> Path:
        """
        Get the reflection file path
        
        Args:
            game_name: Game name
            format: File format (json or txt)
        
        Returns:
            File path
        """
        if format == "json":
            return self.base_path / f"{game_name}_reflections.json"
        elif format == "txt":
            return self.base_path / f"{game_name}_reflections.txt"
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def save_reflection(
        self,
        game_name: str,
        reflection_text: str,
        metadata: Optional[Dict] = None,
        format: str = "json",
        max_length: int = 2000,
        replace: bool = True
    ) -> bool:
        """
        Save reflection
        
        Args:
            game_name: Game name
            reflection_text: Reflection text
            metadata: Metadata (e.g., video path, generation time, etc.)
            format: Save format (json or txt)
            max_length: Maximum text length in words (not characters)
            replace: If True, replace the entire file; if False, append to existing reflections
        
        Returns:
            Whether the save was successful
        """
        try:
            # Limit text length by word count (approximate, since token counting requires tokenizer)
            words = reflection_text.split()
            if len(words) > max_length:
                reflection_text = ' '.join(words[:max_length])
            
            if format == "json":
                return self._save_json(game_name, reflection_text, metadata, replace=replace)
            elif format == "txt":
                return self._save_txt(game_name, reflection_text, replace=replace)
            else:
                logger.error(f"Unsupported format: {format}")
                return False
        except Exception as e:
            logger.error(f"Failed to save reflection: {e}")
            return False
    
    def _save_json(self, game_name: str, reflection_text: str, metadata: Optional[Dict] = None, replace: bool = True) -> bool:
        """Save as JSON format"""
        file_path = self.get_reflection_path(game_name, "json")
        
        # Create new reflection
        new_reflection = {
            "text": reflection_text,
            "metadata": metadata or {}
        }
        
        if replace:
            # Replace entire file with new reflection
            reflections = [new_reflection]
        else:
            # Read existing reflections and append
            existing_reflections = []
            if file_path.exists():
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if isinstance(data, list):
                            existing_reflections = data
                        elif isinstance(data, dict) and "reflections" in data:
                            existing_reflections = data["reflections"]
                except Exception as e:
                    logger.warning(f"Failed to read existing reflections: {e}")
            reflections = existing_reflections + [new_reflection]
        
        # Save
        # Summary should only contain the current reflection, not all historical reflections
        data = {
            "game_name": game_name,
            "reflections": reflections,
            "summary": self._create_summary([new_reflection])  # Only create summary from current reflection
        }
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Reflection saved to: {file_path}")
        return True
    
    def _save_txt(self, game_name: str, reflection_text: str, replace: bool = True) -> bool:
        """Save as TXT format"""
        file_path = self.get_reflection_path(game_name, "txt")
        
        if replace:
            # Replace entire file
            mode = 'w'
        else:
            # Append mode
            mode = 'a'
        
        with open(file_path, mode, encoding='utf-8') as f:
            if not replace:
                f.write(f"\n{'='*50}\n")
            f.write(f"Game: {game_name}\n")
            f.write(f"{'='*50}\n\n")
            f.write(reflection_text)
            f.write("\n\n")
        
        logger.info(f"Reflection saved to: {file_path}")
        return True
    
    def load_reflection(self, game_name: str = None, format: str = "json", file_path: Optional[str] = None) -> Tuple[Optional[str], Optional[Dict]]:
        """
        Load reflection
        
        Args:
            game_name: Game name (used if file_path is not provided)
            format: File format (used if file_path is not provided)
            file_path: Directly specify reflection file path (takes priority)
        
        Returns:
            Tuple of (Reflection text, Metadata), or (None, None) if it doesn't exist
        """
        # If file_path is provided, use it directly; otherwise build path from game_name and format
        if file_path:
            reflection_path = Path(file_path)
            # Determine format from file extension
            if reflection_path.suffix == '.json':
                format = "json"
            elif reflection_path.suffix == '.txt':
                format = "txt"
        else:
            if not game_name:
                logger.error("Must provide game_name or file_path")
                return None, None
            reflection_path = self.get_reflection_path(game_name, format)
        
        if not reflection_path.exists():
            logger.warning(f"Reflection file does not exist: {reflection_path}")
            return None, None
        
        try:
            if format == "json":
                with open(reflection_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                    # Log loaded reflection info
                    logger.info(f"Loaded reflection from: {reflection_path}")
                    
                    if isinstance(data, dict):
                        # Try to extract metadata
                        metadata = None
                        if "reflections" in data and isinstance(data["reflections"], list) and len(data["reflections"]) > 0:
                            # Use metadata from the last reflection as representative
                            last_reflection = data["reflections"][-1]
                            if isinstance(last_reflection, dict) and "metadata" in last_reflection:
                                metadata = last_reflection["metadata"]
                        
                        if "summary" in data:
                            summary = data["summary"]
                            return self._extract_content_from_text(summary), metadata
                    
                    # Fallback for old list format
                    if isinstance(data, list):
                        # Merge all reflections
                        texts = [r.get("text", "") for r in data if isinstance(r, dict)]
                        
                        # Try to get metadata from last item
                        metadata = None
                        if len(data) > 0 and isinstance(data[-1], dict) and "metadata" in data[-1]:
                            metadata = data[-1]["metadata"]
                            
                        extracted_texts = [self._extract_content_from_text(text) for text in texts]
                        return "\n".join(extracted_texts), metadata
                    else:
                        return self._extract_content_from_text(str(data)), None
            elif format == "txt":
                with open(reflection_path, 'r', encoding='utf-8') as f:
                    return f.read(), None
            else:
                logger.error(f"Unsupported format: {format}")
                return None, None
        except Exception as e:
            logger.error(f"Failed to load reflection: {e}")
            return None, None
    
    def _extract_content_from_text(self, text: str) -> str:
        """
        Extract actual content from text
        If the text is a string representation of a ChatCompletion object, extract the content field
        
        Args:
            text: May be a ChatCompletion string or plain text
        
        Returns:
            Extracted content text
        """
        if not text:
            return ""
        
        # Check if it's a string representation of a ChatCompletion object
        # Format is usually: ChatCompletion(..., message=ChatCompletionMessage(content='...', ...))
        # Try to extract content from content='...'
        # Use a more precise pattern: content=' starts, ends at ', refusal=None or ', role='
        content_match = re.search(r"content=['\"](.*?)(?=['\"],\s*(?:refusal|role)=)", text, re.DOTALL)
        if content_match:
            # Extract content field value, handle escape characters
            content = content_match.group(1)
            # Handle escape characters
            content = content.replace('\\n', '\n').replace('\\t', '\t').replace('\\"', '"').replace("\\'", "'")
            return content
        
        # If not ChatCompletion format, return original text
        return text
    
    def _create_summary(self, reflections: List[Dict]) -> str:
        """
        Create a summary from multiple reflections
        
        Args:
            reflections: List of reflections
        
        Returns:
            Summary text
        """
        if not reflections:
            return ""
        
        # Extract all reflection texts and extract actual content
        texts = []
        for r in reflections:
            if isinstance(r, dict) and "text" in r:
                text = r.get("text", "")
                # Extract actual content from text
                extracted_content = self._extract_content_from_text(text)
                texts.append(extracted_content)
        
        # Simple merge, deduplicate similar content
        unique_texts = []
        for text in texts:
            # Simple deduplication logic: skip if new text is very similar to existing text
            is_duplicate = False
            for existing in unique_texts:
                # Simple similarity check: if most of the new text is already in existing text, consider it duplicate
                if len(text) > 0 and len(existing) > 0:
                    overlap = len(set(text.split()) & set(existing.split()))
                    similarity = overlap / max(len(set(text.split())), len(set(existing.split())))
                    if similarity > 0.8:  # 80% similarity threshold
                        is_duplicate = True
                        break
            
            if not is_duplicate:
                unique_texts.append(text)
        
        # Merge and limit length
        summary = "\n\n".join(unique_texts)
        
        # 将 summary 的长度限制为最多 10000 个按空格切分的“单词”
        # 注意：这里只是粗略按空格 split，主要目的是和上游 max_length 语义保持一致
        max_words = 10000
        words = summary.split()
        if len(words) > max_words:
            summary = " ".join(words[:max_words]) + "..."
        
        return summary
    
    def has_reflection(self, game_name: str, format: str = "json") -> bool:
        """Check if reflection file exists"""
        file_path = self.get_reflection_path(game_name, format)
        return file_path.exists()

