import os
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

@dataclass
class Isotope:
    protons: int
    nucleons: int
    radioactive: str
    element: str
    name: str
    spin: float
    gn: float
    abundance: float
    qm: float

    @property
    def symbol(self) -> str:
        return f"{self.nucleons}{self.element}"


class IsotopeDatabase:
    def __init__(self, data_file: Optional[str] = None):
        if data_file is None:
            data_file = os.path.join(os.path.dirname(__file__), "isotopedata.txt")
        self.isotopes: Dict[str, Isotope] = {}
        self._load_data(data_file)

    def _load_data(self, data_file: str):
        with open(data_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('%'):
                    continue
                # Split line by whitespace
                parts = line.split()
                if len(parts) >= 9:
                    try:
                        protons = int(parts[0])
                        nucleons = int(parts[1])
                        radioactive = parts[2]
                        element = parts[3]
                        name = parts[4]
                        spin = float(parts[5])
                        gn = float(parts[6])
                        abundance = float(parts[7])
                        qm = float(parts[8])
                        
                        iso = Isotope(
                            protons=protons,
                            nucleons=nucleons,
                            radioactive=radioactive,
                            element=element,
                            name=name,
                            spin=spin,
                            gn=gn,
                            abundance=abundance,
                            qm=qm
                        )
                        self.isotopes[iso.symbol] = iso
                    except ValueError:
                        continue

    def get_isotope(self, symbol: str) -> Isotope:
        # If user just passes the element (e.g., 'C'), we could return the most abundant
        # For simplicity, we expect the explicit symbol like '13C', but let's add basic support
        if symbol in self.isotopes:
            return self.isotopes[symbol]
        
        # If just element is passed, find most abundant isotope
        candidates = [iso for iso in self.isotopes.values() if iso.element == symbol]
        if candidates:
            return max(candidates, key=lambda x: x.abundance)
            
        raise ValueError(f"Isotope {symbol} not found in database.")

    def get_spin(self, symbol: str) -> float:
        return self.get_isotope(symbol).spin

    def get_gn(self, symbol: str) -> float:
        return self.get_isotope(symbol).gn

    def get_qm(self, symbol: str) -> float:
        return self.get_isotope(symbol).qm

# Global singleton instance
_db = None

def _get_db() -> IsotopeDatabase:
    global _db
    if _db is None:
        _db = IsotopeDatabase()
    return _db

def nucspin(symbol: str) -> float:
    return _get_db().get_spin(symbol)

def nucgval(symbol: str) -> float:
    return _get_db().get_gn(symbol)

def nucqmom(symbol: str) -> float:
    return _get_db().get_qm(symbol)
