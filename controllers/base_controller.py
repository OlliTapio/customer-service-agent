from abc import ABC, abstractmethod
from typing import Any, Dict

class BaseController(ABC):
    """Base class for all controllers in the system."""
    
    @abstractmethod
    def process_input(self, input_data: Dict[str, Any]) -> None:
        """
        Process input data and generate appropriate response.
        
        Args:
            input_data: Dictionary containing the input data to process
        """
        pass 