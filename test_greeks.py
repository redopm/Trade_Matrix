import sys
import os

# Add backend directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'backend')))

from app.services.greeks import GreeksCalculator

print("CE ITM:", GreeksCalculator.calculate_greeks("CE", 21500, 21000, 5, 600))
print("CE OTM:", GreeksCalculator.calculate_greeks("CE", 21500, 22000, 5, 50))
print("PE ITM:", GreeksCalculator.calculate_greeks("PE", 21500, 22000, 5, 600))
print("PE OTM:", GreeksCalculator.calculate_greeks("PE", 21500, 21000, 5, 50))
