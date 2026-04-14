"""
PLC Communication Module
Handles communication with Allen-Bradley PLCs using pycomm3
"""

import logging
from typing import Optional, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PLCResult:
    """Result from a PLC operation"""
    success: bool
    value: Any = None
    data_type: Optional[str] = None
    error: Optional[str] = None


class PLCCommunicator:
    """
    Handles PLC communication using pycomm3
    Gracefully degrades if pycomm3 not installed
    """
    
    def __init__(self):
        """Initialize PLC communicator"""
        self.pycomm3_available = False
        self.LogixDriver = None
        self.Micro800Driver = None
        
        try:
            from pycomm3 import LogixDriver
            self.LogixDriver = LogixDriver
            self.pycomm3_available = True
            logger.info("pycomm3 loaded: LogixDriver available")
            
            # Try to import Micro800Driver (available in pycomm3 1.3.0+)
            try:
                from pycomm3 import Micro800Driver
                self.Micro800Driver = Micro800Driver
                logger.info("pycomm3: Micro800Driver available")
            except ImportError:
                logger.info("pycomm3: Micro800Driver not available (requires pycomm3 >= 1.3.0) - will use LogixDriver for Micro800 PLCs")
                
        except ImportError as e:
            logger.warning(f"pycomm3 import failed: {e}")
            logger.warning("PLC communication disabled")
    
    def is_available(self) -> bool:
        """Check if pycomm3 is available"""
        return self.pycomm3_available
    
    def test_connection(self, ip_address: str, slot: int = 0, plc_type: str = 'CompactLogix') -> bool:
        """
        Test connection to PLC
        
        Args:
            ip_address: PLC IP address
            slot: Slot number (default 0)
            plc_type: Type of PLC (CompactLogix, ControlLogix, MicroLogix, Micro800)
        
        Returns:
            True if connection successful
        """
        if not self.is_available():
            logger.error("Cannot test connection - pycomm3 not available")
            return False
        
        try:
            # Determine PLC driver class with graceful fallback
            if plc_type == 'Micro800' and self.Micro800Driver:
                plc_class = self.Micro800Driver
            else:
                # LogixDriver handles CompactLogix, ControlLogix, MicroLogix
                # Also used as fallback for Micro800 if Micro800Driver unavailable
                plc_class = self.LogixDriver
            
            with plc_class(ip_address, slot=slot) as plc:
                # Try to read identity
                identity = plc.get_plc_info()
                if identity:
                    logger.info(f"Connection successful to {ip_address}: {identity}")
                    return True
                return False
                
        except Exception as e:
            logger.error(f"Connection test failed for {ip_address}: {e}")
            return False
    
    def read_tag(self, ip_address: str, tag_name: str, slot: int = 0, plc_type: str = 'CompactLogix') -> PLCResult:
        """
        Read a tag value from PLC
        
        Args:
            ip_address: PLC IP address
            tag_name: Tag name to read
            slot: Slot number (default 0)
            plc_type: Type of PLC
        
        Returns:
            PLCResult with value and status
        """
        # FIX: Ensure slot is an integer
        slot = int(slot) if not isinstance(slot, int) else slot
        
        if not self.is_available():
            return PLCResult(success=False, error="pycomm3 not installed")
        
        try:
            # Determine PLC driver class with graceful fallback
            if plc_type == 'Micro800' and self.Micro800Driver:
                plc_class = self.Micro800Driver
            else:
                # LogixDriver handles CompactLogix, ControlLogix, MicroLogix
                # Also used as fallback for Micro800 if Micro800Driver unavailable
                plc_class = self.LogixDriver
            
            with plc_class(ip_address, slot=slot) as plc:
                result = plc.read(tag_name)
                
                if result.error:
                    logger.error(f"Read failed for {tag_name} on {ip_address}: {result.error}")
                    return PLCResult(success=False, error=str(result.error))
                
                logger.info(f"Read successful: {tag_name} = {result.value}")
                return PLCResult(
                    success=True,
                    value=result.value,
                    data_type=str(result.type) if hasattr(result, 'type') else None
                )
                
        except Exception as e:
            logger.error(f"Read failed for {tag_name} on {ip_address}: {e}")
            return PLCResult(success=False, error=str(e))
    
    def write_tag(self, ip_address: str, tag_name: str, value: Any, slot: int = 0, plc_type: str = 'CompactLogix') -> PLCResult:
        """
        Write a value to a PLC tag
        
        Args:
            ip_address: PLC IP address
            tag_name: Tag name to write
            value: Value to write
            slot: Slot number (default 0)
            plc_type: Type of PLC
        
        Returns:
            PLCResult with status
        """
        # FIX: Ensure slot is an integer
        slot = int(slot) if not isinstance(slot, int) else slot
        
        if not self.is_available():
            return PLCResult(success=False, error="pycomm3 not installed")
        
        try:
            # Determine PLC driver class with graceful fallback
            if plc_type == 'Micro800' and self.Micro800Driver:
                plc_class = self.Micro800Driver
            else:
                # LogixDriver handles CompactLogix, ControlLogix, MicroLogix
                # Also used as fallback for Micro800 if Micro800Driver unavailable
                plc_class = self.LogixDriver
            
            with plc_class(ip_address, slot=slot) as plc:
                result = plc.write(tag_name, value)
                
                if result.error:
                    logger.error(f"Write failed for {tag_name} on {ip_address}: {result.error}")
                    return PLCResult(success=False, error=str(result.error))
                
                logger.info(f"Write successful: {tag_name} = {value}")
                return PLCResult(success=True)
                
        except Exception as e:
            logger.error(f"Write failed for {tag_name} on {ip_address}: {e}")
            return PLCResult(success=False, error=str(e))
    
    def get_tag_list(self, ip_address: str, slot: int = 0, plc_type: str = 'CompactLogix') -> Optional[list]:
        """
        Get list of tags from PLC
        
        Args:
            ip_address: PLC IP address
            slot: Slot number (default 0)
            plc_type: Type of PLC
        
        Returns:
            List of tag names or None if failed
        """
        # FIX: Ensure slot is an integer
        slot = int(slot) if not isinstance(slot, int) else slot
        
        if not self.is_available():
            logger.error("Cannot get tag list - pycomm3 not available")
            return None
        
        try:
            # Determine PLC driver class with graceful fallback
            if plc_type == 'Micro800' and self.Micro800Driver:
                plc_class = self.Micro800Driver
            else:
                # LogixDriver handles CompactLogix, ControlLogix, MicroLogix
                # Also used as fallback for Micro800 if Micro800Driver unavailable
                plc_class = self.LogixDriver
            
            with plc_class(ip_address, slot=slot) as plc:
                tags = plc.get_tag_list()
                logger.info(f"Retrieved {len(tags)} tags from {ip_address}")
                return tags
                
        except Exception as e:
            logger.error(f"Failed to get tag list from {ip_address}: {e}")
            return None


def initialize_plc_communicator() -> PLCCommunicator:
    """Initialize and return PLC communicator"""
    try:
        comm = PLCCommunicator()
        if comm.is_available():
            logger.info("PLC communicator initialized with pycomm3")
        else:
            logger.warning("PLC communicator initialized in simulation mode (pycomm3 not available)")
        return comm
    except Exception as e:
        logger.error(f"Failed to initialize PLC communicator: {e}")
        raise